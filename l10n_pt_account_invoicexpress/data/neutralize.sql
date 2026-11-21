-- disable InvoiceXpress connection
UPDATE account_journal
   SET invoicexpress_api_key = NULL
 WHERE invoicexpress_api_key IS NOT NULL;
