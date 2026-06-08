.PHONY: install data dbt-build dbt-test run all clean

install:
	pip install -r requirements.txt

data:
	python3 data/generate_data.py

dbt-build:
	cd dbt && dbt deps && dbt seed && dbt run

dbt-test:
	cd dbt && dbt test

run:
	streamlit run app/streamlit_app.py

all: data dbt-build dbt-test run

clean:
	rm -f gtm_revenue.duckdb
	rm -rf dbt/target dbt/dbt_packages
