"""Print the first few forward-adjusted daily bars for one symbol.

Run from the backend directory:

    uv run python strategies/example.py
"""

from tick.research import daily_bars


def main() -> None:
    table = daily_bars("000001.SZ")
    print(table.slice(0, 3))


if __name__ == "__main__":
    main()
