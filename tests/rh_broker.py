from StratDaemon.integration.broker.robinhood import RobinhoodBroker

broker = RobinhoodBroker()
df = broker.get_crypto_historical("DOGE", "5minute", "week")
df = df.sort_values("timestamp", ascending=True)
df.to_json("rh_historical_data.json")
