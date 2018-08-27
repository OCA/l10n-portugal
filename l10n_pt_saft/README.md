Implementação da versão portuguesa do Ficheiro para auditoria fiscal
====================================================================

SAFT - Standard Audit File for Tax purposes
Módulo l10n_pt_saft.


Notas
------

Implementa a exportação de um ficheiro de dados para efeitos de auditoria fiscal, de acordo com a 
Portaria 1192/2009 de 8 de Outubro do Ministério das Finanças.

Estão implementados todos os campos obrigatórios.
O assistente de exportação do ficheiro encontra-se no menu Gestão Financeira/Mapas Oficiais

Modificações a tabelas:

    res.partner
        Adicionados campos 'reg_com' e 'conservatoria' para registar os dados do registo comercial 
        dos parceiros
        self_bill_sales e self_bill_puch para assinalar a existencia de acordos de auto-facturação para vendas e/ou compras

    res.company
        Adicionado campo 'open_journal' para especificar o diário de abertura. Os movimentos deste 
        diário são filtrados. 
        Acessível no menu: Administração/Utilizadores/Estrutura da empresa/Empresas -> configuração.

    account.tax
        Novos campos 'country_region' e 'saft_tax_type', 'saft_tax_code', 'expiration_date' e 'exemption_reason' 
        para cumprir com a especificação da tabela fiscal.
        É obrigatório inserir um codigo de iva nas facturas, para preencher o motivo da isenção no saft, quando o valor é zero

    account.invoice
        campos hash, hash_control e system_entry_date - para registo da assinatura digital, versao da chave e data de confirmação da factura

    account.journal
        'self_billing', 'transaction_type' e 'saft_inv_type' para indicar se o diario refere-se a lançamentos de auto-facturação,
                   a classificar oa facturas e lançamentos conforme os tipos definidos no saft.

Falta implementar campos relativos à ordem de compra do cliente que originou a factura e informação 
sobre local e data de carga e descarga das mercadorias
