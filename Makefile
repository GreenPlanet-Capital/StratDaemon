
run:
	strat-daemon start --path-to-currency-codes examples/sample_currencies.txt \
					   --path-to-holdings examples/sample_holdings.json \
					   --no-paper-trade --auto-generate-orders \
					   --max-amount-per-order 25 --strategy fib_vol_rsi

run-paper:
	strat-daemon start --path-to-currency-codes examples/sample_currencies.txt \
					   --paper-trade --auto-generate-orders \
					   --max-amount-per-order 100 --strategy fib_vol_rsi

get-results:
	python tests/get_results.py $(ORDER)

test: clean
	python tests/back_tester.py

test-full: clean-full
	PYTHONPATH="${PYTHONPATH}:ml" python tests/full_back_tester.py $(TYPE)

test-ml:
	PYTHONPATH="${PYTHONPATH}:tests" python ml/tuning/test.py

vis-ml:
	optuna-dashboard sqlite:///optuna_db.sqlite3

clean-full:
	rm -f results/performance_full.csv

clean:
	rm -f results/performance.csv results/*.png

pull:
	python tests/pull_data.py
