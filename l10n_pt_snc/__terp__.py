# -*- coding: utf-8 -*-
{
	"name" : "Portugal : POC - Plano Oficial de Contabilidade",
    'description': """Plano de contas e básico segundo o POC em vigor até 2009""",
	"version" : "0.1",
	"author" : "Paulino Ascenção<paulino1@sapo.pt>",
	"website": "",
	"category" : "Localisation/Account charts",
	"depends" : ["account"],
	"init_xml" : [
                "account.account.type.csv",
                "account.account.csv", 
                "account.tax.code.csv",
                "account.tax.csv",
                "ir.sequence.type.csv",
                "ir.sequence.csv",
                "account_journal_view.xml",
                "account.journal.csv",
                "res.partner.csv",
                "res.partner.address.csv",
                ],
	"demo_xml" : [],
	"update_xml" : [            ], 
	"installable": True
}
