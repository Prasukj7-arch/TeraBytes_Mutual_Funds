from app.services.portfolio_service import seed_portfolio_data


if __name__ == "__main__":
    count = seed_portfolio_data()
    print(f"Portfolio table ready with {count} records")
