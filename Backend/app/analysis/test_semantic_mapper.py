import json

from app.analysis.semantic_mapper import (
    inspect_semantic_map,
)


def main():

    result = inspect_semantic_map()

    print("\n===== BASE DE DATOS =====")
    print(result["database"])

    print("\n===== MAPA SEMÁNTICO =====")

    print(
        json.dumps(
            result["semantic_map"],
            indent=4,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()