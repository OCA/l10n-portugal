-- disable InvoiceXpress connection
UPDATE res_company
   SET invoicexpress_account_name = NULL
 WHERE invoicexpress_account_name IS NOT NULL;
