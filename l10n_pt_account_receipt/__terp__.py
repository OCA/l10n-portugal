{
	"name" : "Receipts Management",
	"version" : "1.0",
	"author" : "Paulino",
    "description": """
            Manages receipts for customers
            
            New receipts are created from a wizard, the views on account.receipt object are readonly
            There should be a journal of type 'cash' with an invoice sequence set to generate receipts numbers
            """,
	"category" : "Generic Modules/Receipts",
	"depends" : ["account"],
	"init_xml" : [],
	"demo_xml" : [],
	"update_xml" : ['receipt_view.xml',  'receipt_report.xml'],
	"active": False,
	"installable": True
}
