import json

from app.analysis.dashboard_service import (
    get_dashboard_summary,
)


def main():

    print("\n===== DASHBOARD =====")

    result = get_dashboard_summary()

    print(
        json.dumps(
            result,
            indent=4,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()