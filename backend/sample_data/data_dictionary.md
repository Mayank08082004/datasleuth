# Transactions Data Dictionary

## transaction_id
Unique identifier for each sales transaction. Format: letter T followed by four digits (e.g. T0001).

## customer_id
Identifier of the customer. Format: letter C followed by three digits. May be blank if the customer is unknown.

## transaction_date
Date the transaction occurred, in YYYY-MM-DD format.

## region
Sales region: North, South, East or West.

## product_category
Product category: Electronics, Clothing, Home or Books.

## quantity
Number of units sold in the transaction.

## unit_price
Price per unit in USD.

## amount
Total transaction value in USD, equal to quantity multiplied by unit price.
