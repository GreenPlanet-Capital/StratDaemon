# StratDaemon
Live monitor for managing financial assets with customized strategies

### Installation

**Developer**

```bash
pip install -e .
cp config.ini config_dev.ini
export ENV=dev
```

### Setup

**Integration**

```bash
git update-index --assume-unchanged config.ini
emacs config.ini # Change values as needed
```

### Usage

Check the `sample.py` script. 

_Note_: You might have to enter Robinhood's 2FA code if you are running this for the first time.
