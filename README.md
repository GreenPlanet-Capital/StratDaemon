# StratDaemon

Live monitor for managing financial assets with customized strategies

## Installation

### Developer

```bash
pip install -e .
cp config.ini config_dev.ini
export ENV=dev
```

### Setup

#### Integration

```bash
git update-index --assume-unchanged config.ini
emacs config.ini # Change values as needed
```

### Usage

Check the `sample.py` script.

### Notes

- You might have to enter Robinhood's 2FA code if you are running this for the first time.

- If you are using Gmail notif integration, you would need to generate an App Password for authentication. You can do this by visiting [Google App Passwords](https://myaccount.google.com/apppasswords). `config.ini` should be updated with the generated password.
