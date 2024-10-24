# StratDaemon
Live monitor for managing financial assets with customized strategies

### Installation

**Developer**



```bash
pip install -e .
```

### Setup

**Integration**

```bash
emacs creds.ini
```

```conf
[robinhood]
email = EMAIL_HERE
password = PASSWORD_HERE
```

### Usage

Check the `sample.py` script. 

_Note_: You might have to enter Robinhood's 2FA code if you are running this for the first time.
