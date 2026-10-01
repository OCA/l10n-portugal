## Demo employees

When the database is created with demo data enabled, the module adds a
full set of employees to the "PT Company" demo company. Switch to that
company and open Employees to see them.

## Load testing

To create large numbers of employees for load testing, use the `odoo populate`
command, which duplicates the existing demo employees:

```console
$ odoo populate -d <database> --models hr.employee --factors 100
```
