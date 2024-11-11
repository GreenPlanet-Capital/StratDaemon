
run:
	strat-daemon start --path-to-currency-codes examples/sample_currencies.txt \
					   --path-to-holdings examples/sample_holdings.json \
					   --no-paper-trade --auto-generate-orders --no-confirm-before-trade \
					   --max-amount-per-order 100 --strategy fib_vol_rsi --poll-interval 1800

run-paper:
	strat-daemon start --path-to-currency-codes examples/sample_currencies.txt \
					   --path-to-holdings examples/sample_holdings.json \
					   --paper-trade --auto-generate-orders --no-confirm-before-trade \
					   --max-amount-per-order 100 --strategy fib_vol_rsi --poll-interval 1800

get-results:
	python tests/get_results.py $(ORDER)

test: clean
	python tests/back_tester.py

clean: check_clean
	rm -f results/performance.csv results/*.png

pull:
	python tests/pull_data.py

check_clean:
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]