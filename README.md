# StratDaemon

Live monitor for managing financial assets with customized strategies

## Installation

```bash
pip install -e .
cp config.ini config_dev.ini
strat-daemon --install-completion zsh
```

## Setup

### Integration

```bash
emacs config_dev.ini # Change values as needed
```

### Usage

#### For Developer

Check the `examples/sample.py` script.

#### For User

- `config_dev.ini` should be updated with your Robinhood credentials and other settings. This should be in directory where you run the below commands.

- Orders should be in JSON format. You can refer to `examples/sample_orders.json` for the structure.

- Currency codes should be in TXT format. You can refer to `examples/sample_currencies.txt` for the structure.

```bash
strat-daemon --help
strat-daemon start --help

# Example with default parameters
strat-daemon start --path-to-orders examples/sample_orders.json --path-to-currency-codes examples/sample_currency_codes.txt
```

### Notes

- You might have to enter Robinhood's 2FA code if you are running this for the first time.

- If you are using Gmail notif integration, you would need to generate an App Password for authentication. You can do this by visiting [Google App Passwords](https://myaccount.google.com/apppasswords). `config.ini` should be updated with the generated password.

### Improvements

- ML model to give confidence score based on past data whether it's a resistance or support level
