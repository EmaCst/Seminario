from app.analysis.capability_detector import (
    inspect_capabilities,
)


def main():

    result = inspect_capabilities()

    print("\n===== BASE DE DATOS =====")
    print(result["database"])

    print("\n===== CAPACIDADES =====")

    for name, info in result[
        "capabilities"
    ].items():

        status = (
            "DISPONIBLE"
            if info["available"]
            else "NO DISPONIBLE"
        )

        print(
            f"\n{name.upper()}: {status}"
        )

        if info["tables"]:

            print(
                "  Tablas detectadas:"
            )

            for table in info["tables"]:
                print(
                    f"    - {table}"
                )


if __name__ == "__main__":
    main()