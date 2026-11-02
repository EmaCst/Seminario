"""Safe bounded Excel formula evaluation for import, without eval or macros."""
from __future__ import annotations

import math
import operator
import re
from datetime import date, datetime
from openpyxl.formula import Tokenizer
from openpyxl.utils.cell import range_boundaries, get_column_letter
from openpyxl.utils.datetime import to_excel, from_excel


class FormulaError(ValueError):
    pass


class UnsupportedFormula(FormulaError):
    pass


REFERENCE = re.compile(
    r"^(?:(?:'((?:[^']|'')+)'|([A-Za-z_][\w .-]*))!)?"
    r"(\$?[A-Za-z]{1,3}\$?[1-9][0-9]{0,6})"
    r"(?::(\$?[A-Za-z]{1,3}\$?[1-9][0-9]{0,6}))?$")
PRECEDENCE = {"=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1,
              "&": 2, "+": 3, "-": 3, "*": 4, "/": 4, "^": 5}
FUNCTIONS = {"SUM", "COUNT", "COUNTA", "AVERAGE", "MIN", "MAX",
             "COUNTIF", "AVERAGEIF", "SUMIF", "COUNTIFS", "SUMIFS",
             "DATEVALUE", "DATE", "YEAR", "MONTH", "DAY",
             "IF", "IFERROR", "AND", "OR", "NOT", "ABS", "INT",
             "ROUND", "ROUNDUP", "ROUNDDOWN", "MOD", "LEN",
             "LEFT", "RIGHT", "CONCAT", "CONCATENATE"}


def number(value):
    if value in (None, ""):
        return 0.0
    if isinstance(value, (date, datetime)):
        return float(to_excel(value))
    if isinstance(value, (int, float, bool)):
        result = float(value)
        if math.isfinite(result):
            return result
    if isinstance(value, str):
        try:
            result = float(value.strip())
            if math.isfinite(result):
                return result
        except ValueError:
            pass
    raise FormulaError("Se esperaba un valor numérico")


def flatten(values):
    for value in values:
        if isinstance(value, list):
            yield from flatten(value)
        else:
            yield value


def criterion_match(value, condition):
    if isinstance(condition, (int, float)):
        return value == condition
    condition = str(condition)
    match = re.match(r"^(<=|>=|<>|=|<|>)(.*)$", condition)
    op, target = (match.group(1), match.group(2)) if match else ("=", condition)
    try:
        a, b = number(value), float(target)
    except (FormulaError, ValueError, TypeError):
        a, b = str(value or "").casefold(), target.casefold()
    if isinstance(a, str) and ("*" in b or "?" in b):
        pattern = "^" + re.escape(b).replace(r"\*", ".*").replace(r"\?", ".") + "$"
        found = re.match(pattern, a, flags=re.I) is not None
        return found if op == "=" else not found if op == "<>" else False
    return {"=": operator.eq, "<>": operator.ne, "<": operator.lt,
            ">": operator.gt, "<=": operator.le, ">=": operator.ge}[op](a, b)


class Parser:
    def __init__(self, formula):
        self.tokens = [t for t in Tokenizer(formula).items if t.type != "WHITE-SPACE"]
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self):
        tok = self.peek()
        if tok is None:
            raise FormulaError("Fórmula incompleta")
        self.pos += 1
        return tok

    def parse(self):
        result = self.expression()
        if self.peek() is not None:
            raise UnsupportedFormula("Sintaxis no admitida")
        return result

    def expression(self, minimum=0):
        tok = self.take()
        if tok.type == "OPERAND":
            if tok.subtype == "NUMBER":
                left = ("literal", float(tok.value))
            elif tok.subtype == "TEXT":
                left = ("literal", tok.value[1:-1].replace('""', '"'))
            elif tok.subtype == "LOGICAL":
                left = ("literal", tok.value.upper() == "TRUE")
            elif tok.subtype == "RANGE":
                left = ("ref", tok.value)
            else:
                raise UnsupportedFormula("Operando no admitido")
        elif tok.type == "OPERATOR-PREFIX" and tok.value in ("+", "-"):
            left = ("unary", tok.value, self.expression(6))
        elif tok.type == "PAREN" and tok.subtype == "OPEN":
            left = self.expression()
            end = self.take()
            if end.type != "PAREN" or end.subtype != "CLOSE":
                raise FormulaError("Paréntesis sin cerrar")
        elif tok.type == "FUNC" and tok.subtype == "OPEN":
            name = tok.value[:-1].upper()
            if name not in FUNCTIONS:
                raise UnsupportedFormula("Función no admitida: " + name)
            args = []
            while not (self.peek() and self.peek().type == "FUNC" and self.peek().subtype == "CLOSE"):
                args.append(self.expression())
                sep = self.peek()
                if sep and sep.type == "SEP" and sep.subtype == "ARG":
                    self.take()
                elif sep and sep.type == "FUNC" and sep.subtype == "CLOSE":
                    break
                else:
                    raise FormulaError("Argumentos inválidos")
            self.take()
            left = ("func", name, args)
        else:
            raise UnsupportedFormula("Sintaxis no admitida")
        while self.peek():
            tok = self.peek()
            if tok.type == "OPERATOR-POSTFIX" and tok.value == "%":
                self.take()
                left = ("percent", left)
                continue
            if tok.type != "OPERATOR-INFIX" or tok.value not in PRECEDENCE:
                break
            prec = PRECEDENCE[tok.value]
            if prec < minimum:
                break
            self.take()
            left = ("binary", tok.value, left, self.expression(prec + (tok.value != "^")))
        return left


class FormulaEvaluator:
    def __init__(self, workbook, *, max_cells=30000, max_depth=80):
        self.workbook = workbook
        self.max_cells = max_cells
        self.max_depth = max_depth
        self.cache = {}
        self.visiting = set()
        self.work = 0

    def value(self, sheet, cell):
        key = (sheet, cell.replace("$", "").upper())
        if key in self.cache:
            return self.cache[key]
        if key in self.visiting:
            raise FormulaError("Referencia circular")
        if len(self.visiting) >= self.max_depth:
            raise FormulaError("Demasiadas dependencias")
        self.work += 1
        if self.work > self.max_cells:
            raise FormulaError("Límite máximo de celdas excedido")
        if sheet not in self.workbook:
            raise FormulaError("Hoja inexistente")
        current = self.workbook[sheet][key[1]]
        if current.data_type != "f":
            return current.value
        self.visiting.add(key)
        try:
            result = self.evaluate(Parser(current.value).parse(), sheet)
            if isinstance(result, list):
                raise UnsupportedFormula("No se admiten rangos como resultado")
            if isinstance(result, float) and not math.isfinite(result):
                raise FormulaError("Resultado numérico inválido")
            self.cache[key] = result
            return result
        finally:
            self.visiting.remove(key)

    def reference(self, text, current_sheet):
        if any(s in text for s in ("[", "]", "#")):
            raise UnsupportedFormula("Referencias externas/estructuradas no admitidas")
        found = REFERENCE.fullmatch(text)
        if found is None:
            raise UnsupportedFormula("Referencia no compatible: " + text[:60])
        quoted, plain, first, last = found.groups()
        sheet = quoted.replace("''", "'") if quoted else plain or current_sheet
        if last is None:
            return self.value(sheet, first)
        c1, r1, c2, r2 = range_boundaries(first + ":" + last)
        count = (c2-c1+1)*(r2-r1+1)
        if count > self.max_cells:
            raise FormulaError("Rango demasiado grande")
        return [self.value(sheet, f"{get_column_letter(c)}{r}")
                for r in range(r1, r2+1) for c in range(c1, c2+1)]

    def evaluate(self, tree, sheet):
        kind = tree[0]
        if kind == "literal":
            return tree[1]
        if kind == "ref":
            return self.reference(tree[1], sheet)
        if kind == "unary":
            value = number(self.evaluate(tree[2], sheet))
            return value if tree[1] == "+" else -value
        if kind == "percent":
            return number(self.evaluate(tree[1], sheet))/100
        if kind == "binary":
            op = tree[1]
            a, b = self.evaluate(tree[2], sheet), self.evaluate(tree[3], sheet)
            if isinstance(a, list) or isinstance(b, list):
                raise FormulaError("No se admite operar directamente con rangos")
            if op == "&":
                return str(a or "") + str(b or "")
            if op in ("=", "<>", "<", ">", "<=", ">="):
                return criterion_match(a, op + str(b))
            x, y = number(a), number(b)
            if op == "+": return x+y
            if op == "-": return x-y
            if op == "*": return x*y
            if op == "/":
                if y == 0: raise FormulaError("División entre cero")
                return x/y
            if op == "^":
                if abs(y)>100 or abs(x)>1e100: raise FormulaError("Exponente excesivo")
                try: return x**y
                except (OverflowError, ValueError): raise FormulaError("Potencia inválida")
        if kind == "func":
            name, argtrees = tree[1], tree[2]
            if name == "IF":
                if len(argtrees) not in (2,3): raise FormulaError("IF requiere 2 o 3 argumentos")
                truth = bool(self.evaluate(argtrees[0], sheet))
                return self.evaluate(argtrees[1 if truth else 2], sheet) if truth or len(argtrees)==3 else False
            if name == "IFERROR":
                if len(argtrees)!=2: raise FormulaError("IFERROR requiere 2 argumentos")
                try: return self.evaluate(argtrees[0], sheet)
                except FormulaError: return self.evaluate(argtrees[1], sheet)
            return self.call(name, [self.evaluate(arg, sheet) for arg in argtrees])
        raise UnsupportedFormula("Expresión desconocida")

    def call(self, name, args):
        raw = list(flatten(args))
        numbers = [number(value) for value in raw
                   if isinstance(value, (float,int,date,datetime)) and not isinstance(value,bool)]
        if name == "SUM": return sum(numbers)
        if name == "COUNT": return len(numbers)
        if name == "COUNTA": return sum(v is not None and v!="" for v in raw)
        if name == "AVERAGE":
            if not numbers: raise FormulaError("AVERAGE sin datos")
            return sum(numbers)/len(numbers)
        if name == "MIN": return min(numbers) if numbers else 0
        if name == "MAX": return max(numbers) if numbers else 0
        if name in ("COUNTIF", "SUMIF", "AVERAGEIF"):
            if len(args) not in (2,3): raise FormulaError("Argumentos inválidos")
            keys = args[0] if isinstance(args[0],list) else [args[0]]
            items = args[2] if len(args)==3 else args[0]
            items = items if isinstance(items,list) else [items]
            if len(items)!=len(keys): raise FormulaError("Rangos de distinto tamaño")
            matched = [v for k,v in zip(keys,items) if criterion_match(k,args[1])]
            if name == "COUNTIF": return len(matched)
            nums = [number(v) for v in matched if isinstance(v,(int,float)) and not isinstance(v,bool)]
            if name == "SUMIF": return sum(nums)
            if not nums: raise FormulaError("AVERAGEIF sin valores numéricos")
            return sum(nums)/len(nums)
        if name in ("COUNTIFS", "SUMIFS"):
            if name == "SUMIFS":
                if len(args)<3 or len(args)%2!=1: raise FormulaError("Argumentos SUMIFS inválidos")
                target, pairs = args[0], args[1:]
            else:
                if len(args)<2 or len(args)%2: raise FormulaError("Argumentos COUNTIFS inválidos")
                target, pairs = None,args
            filters = [(pairs[i] if isinstance(pairs[i],list) else [pairs[i]],pairs[i+1]) for i in range(0,len(pairs),2)]
            n=len(filters[0][0])
            if any(len(v)!=n for v,_ in filters): raise FormulaError("Rangos distintos")
            selected = [i for i in range(n) if all(criterion_match(v[i],c) for v,c in filters)]
            if name == "COUNTIFS": return len(selected)
            target = target if isinstance(target,list) else [target]
            if len(target)!=n: raise FormulaError("SUMIFS rangos incompatibles")
            return sum(number(target[i]) for i in selected)
        if name == "DATEVALUE":
            if len(args)!=1: raise FormulaError("DATEVALUE requiere fecha")
            try: return float(to_excel(date.fromisoformat(str(args[0]).strip())))
            except ValueError: raise FormulaError("Fecha inválida")
        if name == "DATE":
            if len(args)!=3: raise FormulaError("DATE requiere 3 argumentos")
            try: return float(to_excel(date(*(int(number(v)) for v in args))))
            except ValueError: raise FormulaError("Fecha inválida")
        if name in ("YEAR", "MONTH", "DAY"):
            if len(args)!=1: raise FormulaError("Función de fecha requiere 1 argumento")
            dt = args[0] if isinstance(args[0],(date,datetime)) else from_excel(number(args[0]))
            return getattr(dt,name.lower())
        if name == "ABS": return abs(number(args[0]))
        if name == "INT": return math.floor(number(args[0]))
        if name == "MOD":
            y=number(args[1])
            if y==0: raise FormulaError("División entre cero")
            return number(args[0])%y
        if name in ("ROUND","ROUNDUP","ROUNDDOWN"):
            digits=int(number(args[1])) if len(args)>1 else 0
            if abs(digits)>10: raise FormulaError("Demasiados decimales")
            n=number(args[0]); factor=10**digits
            fn=math.floor if name=="ROUNDDOWN" else math.ceil
            return math.copysign(fn(abs(n)*factor),n)/factor if name!="ROUND" else math.copysign(math.floor(abs(n)*factor+0.5),n)/factor
        if name == "AND": return all(bool(v) for v in raw)
        if name == "OR": return any(bool(v) for v in raw)
        if name == "NOT": return not bool(args[0])
        if name == "LEN": return len(str(args[0] or ""))
        if name == "LEFT": return str(args[0] or "")[:int(number(args[1])) if len(args)>1 else 1]
        if name == "RIGHT": return str(args[0] or "")[-(int(number(args[1])) if len(args)>1 else 1):]
        if name in ("CONCAT","CONCATENATE"): return "".join(str(v) for v in raw if v is not None)
        raise UnsupportedFormula("Función no admitida: "+name)

    def calculate(self):
        count=0
        errors=[]
        for sheet in self.workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type!="f": continue
                    count+=1
                    try: self.value(sheet.title,cell.coordinate)
                    except (FormulaError,ValueError,TypeError,ArithmeticError) as err:
                        errors.append({"sheet":sheet.title,"cell":cell.coordinate,
                                       "formula":cell.value[:160],"reason":str(err)[:160]})
        return {"formulas_detected":count,"formulas_calculated":count-len(errors),
                "formulas_unresolved":len(errors),"errors":errors[:60],
                "truncated_errors":max(0,len(errors)-60)}
