
run: clean
	python tests/back_tester.py

clean: check_clean
	rm -f results/performance.csv results/*.png

check_clean:
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]