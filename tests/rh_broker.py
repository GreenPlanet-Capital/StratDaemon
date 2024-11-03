from StratDaemon.integration.broker.robinhood import RobinhoodBroker

CRYPO_CURRENCY = "LINK"

broker = RobinhoodBroker()
df = broker.get_crypto_historical(CRYPO_CURRENCY, "hour", "week")
df = df.sort_values("timestamp", ascending=True)
df.to_json(f"rh_{CRYPO_CURRENCY}_historical_data.json")
