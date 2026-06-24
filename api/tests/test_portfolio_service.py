import unittest

from app.services.portfolio_service import (
    create_portfolio_record,
    delete_portfolio_record,
    get_portfolio_by_user,
    seed_portfolio_data,
    update_portfolio_record,
)


class PortfolioServiceTests(unittest.TestCase):
    def setUp(self):
        self.user_id = "TESTUSER"
        self.created_ids = []
        seed_portfolio_data()

    def test_portfolio_crud_flow(self):
        created = create_portfolio_record(
            {
                "user_id": self.user_id,
                "investor_name": "Test Investor",
                "risk_profile": "Moderate",
                "scheme_code": "1999",
                "scheme_name": "Test Fund",
                "units": 250,
                "purchase_nav": 40,
                "current_nav": 48,
                "invested_amount": 10000,
                "current_value": 12000,
                "purchase_date": "2024-01-10",
            }
        )
        self.created_ids.append(created["portfolio_id"])

        portfolio = get_portfolio_by_user(self.user_id)
        self.assertTrue(any(holding["scheme_name"] == "Test Fund" for holding in portfolio["holdings"]))

        updated = update_portfolio_record(created["portfolio_id"], {"current_nav": 50, "current_value": 12500})
        self.assertTrue(updated["updated"])

        deleted = delete_portfolio_record(created["portfolio_id"])
        self.assertTrue(deleted)

    def tearDown(self):
        for portfolio_id in self.created_ids:
            delete_portfolio_record(portfolio_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
