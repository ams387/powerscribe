# PS360python
Powerscribe 360 API python implementation

***Requirements***
1. xmltodict
2. typing
3. datetime
4. jupyter notebook (if testing notebook need be run)

***Basic Implementation***  
1. Create a `creds.py` file from `creds_sample.py`
2. Import a service class: `from ps360_SOAP_12 import CustomFieldService`
3. Start the service: `customfield = CustomFieldService(creds.url, creds.username, creds.password)`
4. Call the functions (e.g. `field_defs = customfield.GetCustomFieldDefinitions('202312042309')`)

