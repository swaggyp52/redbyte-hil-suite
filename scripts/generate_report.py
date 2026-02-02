from src.report_generator import generate_report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("session", help="Path to session JSON")
    parser.add_argument("--out", default="reports", help="Output directory")
    args = parser.parse_args()

    path = generate_report(args.session, args.out)
    print(f"Report generated: {path}")
