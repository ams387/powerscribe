import requests
import xmltodict
import re
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from typing import Any, Dict
from enum import Enum
import warnings

class SoapResponseStatus(Enum):
    SUCCESS = 200
    CLIENT_ERROR = 'soap:Client'
    SERVER_ERROR = 'soap:Server'


class SoapService:
    def __init__(self, root_url, username, password):
        self.root_url = root_url
        self.username = username
        self.password = password

    def make_soap_request(self, service_path: str, soap_body: str) -> Dict[str, Any]:
        headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
        soap_request = self.build_soap_request(soap_body)
        full_url = self.root_url + service_path  # Combine the root URL with the service path
        try:
            response = requests.post(full_url, headers=headers, data=soap_request)
            return self._parse_soap_response(response)
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect: {e}")
        
    def _parse_soap_response(self, response: requests.Response) -> Dict[str, Any]:
        if response.status_code != SoapResponseStatus.SUCCESS.value:
            raise Exception(f"Request failed with status code {response.status_code}")

        response_dict = xmltodict.parse(response.text)
        soap_body = response_dict.get('soap:Body', {})
        if 'soap:Fault' in soap_body:
            self._handle_soap_fault(soap_body['soap:Fault'])

        return response_dict
    
    def _handle_soap_fault(self, fault: Dict[str, Any]) -> None:
        fault_code = fault.get('faultcode')
        fault_string = fault.get('faultstring')
        detail = fault.get('detail')
        if fault_code == SoapResponseStatus.CLIENT_ERROR.value:
            raise ValueError(f"Client error: {fault_string} - {detail}")
        elif fault_code == SoapResponseStatus.SERVER_ERROR.value:
            raise Exception(f"Server error: {fault_string}")

    def build_soap_request(self, soap_body):
        return f"""<?xml version="1.0" encoding="utf-8"?>
            <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
            <soap12:Header>
                <AuthHeader xmlns="{self.NAMESPACE}">
                <SystemID>0</SystemID>
                <AccessCode></AccessCode>
                <Username>{self.username}</Username>
                <Password>{self.password}</Password>
                </AuthHeader>
            </soap12:Header>
            <soap12:Body>
                {soap_body}
            </soap12:Body>
            </soap12:Envelope>"""

class InputValidator:
    @staticmethod
    def validate_input(value, valid_values=None, expected_type=None, param_name=''):
        """
        Generic validation method for input values. Can validate against a list of valid values or a specific type.
        """
        # Validate against a list of valid values
        if valid_values is not None:
            if value not in valid_values:
                raise ValueError(f"Invalid {param_name}: {value}. Must be one of {valid_values}")

        # Validate the type of the value
        if expected_type is not None:
            if not isinstance(value, expected_type):
                raise TypeError(f"'{param_name}' must be a {expected_type.__name__}, got {type(value).__name__}")

        # If neither condition is provided, the method does nothing (could also raise an error)

class DateParser:
    # Define the regex pattern of a relative date
    RELATIVE_DATE_PATTERN = r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s*(ago)?'

    @staticmethod
    def parse_date(date_str):
        """Parse various date formats and relative date strings into ISO format."""
        if isinstance(date_str, str):
            if re.search(DateParser.RELATIVE_DATE_PATTERN, date_str, re.IGNORECASE):
                return DateParser._parse_relative_date(date_str)
            else:
                return DateParser._parse_absolute_date(date_str)
        elif isinstance(date_str, datetime):
            return date_str.isoformat()
        else:
            raise TypeError("Invalid date type provided")

    @staticmethod
    def _parse_relative_date(date_str):
        """Parse a relative date string (e.g., '2 hours ago', '1 month') into ISO format."""
        match = re.match(DateParser.RELATIVE_DATE_PATTERN, date_str, re.IGNORECASE)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if not unit.endswith('s'):
                unit += 's'

            delta_args = {unit: amount}
            return (datetime.now() - relativedelta(**delta_args)).isoformat()
        else:
            raise ValueError(f"Invalid relative date format: {date_str}")
    
    @staticmethod
    def _parse_absolute_date(date_str):
        try:
            return parser.parse(date_str).isoformat()
        except ValueError:
            raise ValueError(f"Date format not recognized: {date_str}")

class CustomFieldService(SoapService):
    NAMESPACE = "http://nuance.com/commissure/webservices/customfield/2008/06"
    
    def GetCustomFieldDefinitions(self, accession: str):
        #site = self.site
        api_call = "GetCustomFieldDefinitions"
        soap_body = f"""
        <{api_call} xmlns="{self.NAMESPACE}">
            <site>UC Davis</site>
            <accession>{accession}</accession>
        </{api_call}>
        """
        return self.make_soap_request("/services/customfield.asmx", soap_body)
    
    def SetOrderCustomFieldByName(self, OrderID: int, FieldName: str,FieldValue:str):
        if FieldName not in ['FluoroTime','AirKerma','KAP']:
            raise Exception('Valid Custom Field Names: FluoroTime, AirKerma, KAP')
        api_call = "SetOrderCustomFieldByName"
        soap_body = f"""
        <{api_call} xmlns="{self.NAMESPACE}">
            <orderID>{OrderID}</orderID>
            <name>{FieldName}</name>
            <value>{FieldValue}</value>
        </{api_call}>
        """
        return self.make_soap_request("/services/customfield.asmx", soap_body)
                            

def parseSearchByAccession(soap_response:dict,data_element:str):
    # OrderID,ReportID - int,
    # Accession,Site,Procedures,Status,Patient,Signer,Dictator- str
    # OrderDate - dateTime (conversion from string needs to be coded!)
    if data_element not in ['OrderID','ReportID','Accession','Site','OrderDate','Procedures','Status','Patient','Signer']:
        raise Exception('Valid Data Elements: OrderID, ReportID, Accession, Site, OrderDate, Procedures, Status, Patient, Signer')
    element_value = soap_response['soap:Envelope']['soap:Body']['SearchByAccessionResponse']['SearchByAccessionResult']['OrderData'][data_element]       
    if data_element in ['OrderID','ReportID']:
        element_value = int(element_value)
    if data_element == 'OrderDate':
        warnings.warn('Function returns a str. DateTime needs to be coded')
    return element_value   
    
class Explorer(SoapService):
    NAMESPACE = "http://nuance.com/commissure/webservices/explorer/2010/06"
    VALID_ORDER_STATUS_OPTIONS = ["All", "Scheduled", "Completed", "Temporary", "Cancelled", "DictatedExt", "Entered"]
    VALID_REPORT_STATUS_OPTIONS = ["All", "WetRead", "Draft", "PendingCorrection", "Corrected", "CorrectionRejected", "PendingSignature", "SignRejected", "Final", "NonFinal", "PendingAddendum", "Addended", "Rejected", "Reported", "Unreported"]
    VALID_TRANSFER_STATUS_OPTIONS = ["All", "Exceptional", "NotReady", "Ready", "Sent", "Rejected", "Failed", "Held", "Queued", "ForceSend"]
    VALID_LOCKING_OPTIONS = ["All", "Locked", "Unlocked", "Assigned", "Unassigned", "LockedOrAssigned", "UnlockedAndUnassigned"]
    VALID_PATIENT_CLASS_OPTIONS = ["All", "Inpatient", "Outpatient", "PreAdmit", "Emergency", "RecurringPatient", "Obstetrics"]
    VALID_PATIENT_AGE_UNIT_OPTIONS = ["Days", "Weeks", "Months", "Years"]
    VALID_PATIENT_AGE_FROM_TYPE = int
    VALID_PATIENT_AGE_TO_TYPE = int
    VALID_SORT_OPTIONS = ["OrderID", "OrderStatus", "ReportID", "ReportStatus", "OrderDate", "Procedures", "ProcedureDesc", "PatientMRN", "PatientMPI", "PatientDeptNumber", "DOB", "Sex", "PatientID", "PatientLastName", "PatientFirstName", "PatientMiddleName", "Accession", "ProviderPhysID", "ProviderLastName", "ProviderFirstName", "ProviderMiddleName", "Status", "SignerAcctID", "SignerLastName", "SignerFirstName", "SignerMiddleName", "DictatorAcctID", "DictatorLastName", "DictatorFirstName", "DictatorMiddleName", "TranscriberAcctID", "TranscriberLastName", "TranscriberFirstName", "TranscriberMiddleName", "ReportTechAcctID", "WetReadAcctID", "LastModified", "IsAddendum", "TransferStatusID", "BIRADSCodeID", "ReportIsImported", "IsFinalExported", "SiteID", "PatientAge", "SiteLocationID", "LocationName", "PatientClassID", "VisitID", "SiteSectionID", "OrderLockAcctID", "LockLastName", "LockFirstName", "LockMiddleName", "AttendingPhysID", "ReferringPhysID", "ConsultingPhysID", "AdmittingPhysID", "Priority", "IsSTAT", "OrderAssignedAcctID", "AssignedLastName", "AssignedFirstName", "AssignedMiddleName", "LastSignDate", "LastCorrectedDate", "LastPrelimDate", "PlacerField1", "PlacerField2", "FillerField1", "FillerField2", "TATDeadline", "OrderIsImported", "OrderCreatorAcctID", "OrderCreateDate", "DICOMSRCount"]

    def SearchByAccession(self, accession: str, sort="OrderDate"):
        api_call = "SearchByAccession"
        soap_body = f"""
        <{api_call} xmlns="{self.NAMESPACE}">
            <site>UC Davis</site>
            <accessions>{accession}</accessions>
            <sort>{sort}</sort> 
        </{api_call}>
        """
        return self.make_soap_request("/services/explorer.asmx", soap_body)
    
    def browse_orders(self, start, end=None, order_status="All", report_status="Final", transfer_status="All", locking="All", patient_class="All", patient_age_unit="Years", patient_age_from=0, patient_age_to=199, account_id=0, site_section_id=0, site_ordering_physician_id=0, site_location_id=0, sort="OrderDate", extended=False):
        start = DateParser.parse_date(start)
        end = DateParser.parse_date(end) if end else datetime.now().isoformat()

        self._validate_input_for_browse_orders(order_status, report_status, transfer_status, locking, patient_class, patient_age_unit, patient_age_from, patient_age_to, sort)
        
        # Determine the SOAP body type
        api_call = "BrowseOrdersEx" if extended else "BrowseOrders"
        
        soap_body = f"""
        <{api_call} xmlns="{self.NAMESPACE}">
            <site></site>
            <timeFrame>
                <Period>Custom</Period>
                <From>{start}</From>
                <To>{end}</To>
            </timeFrame>
            <orderStatus>{order_status}</orderStatus>
            <reportStatus>{report_status}</reportStatus>
            <transferStatus>{transfer_status}</transferStatus>
            <locking>{locking}</locking>
            <patientClass>{patient_class}</patientClass>
            <patientAge>
                <Unit>{patient_age_unit}</Unit>
                <From>{patient_age_from}</From>
                <To>{patient_age_to}</To>
            </patientAge>
            <accountID>{account_id}</accountID>
            <siteSectionID>{site_section_id}</siteSectionID>
            <siteOrderingPhysicianID>{site_ordering_physician_id}</siteOrderingPhysicianID>
            <siteLocationID>{site_location_id}</siteLocationID>
            <sort>{sort}</sort> 
        </{api_call}>
        """
        return self.make_soap_request("/services/explorer.asmx", soap_body)
    
    def _validate_input_for_browse_orders(self, order_status, report_status, transfer_status, locking, patient_class, patient_age_unit, patient_age_from, patient_age_to, sort):
        InputValidator.validate_input(order_status, valid_values=self.VALID_ORDER_STATUS_OPTIONS, param_name="order status")
        InputValidator.validate_input(report_status, valid_values=self.VALID_REPORT_STATUS_OPTIONS, param_name="report status")
        InputValidator.validate_input(transfer_status, valid_values=self.VALID_TRANSFER_STATUS_OPTIONS, param_name="transfer status")
        InputValidator.validate_input(locking, valid_values=self.VALID_LOCKING_OPTIONS, param_name="locking")
        InputValidator.validate_input(patient_class, valid_values=self.VALID_PATIENT_CLASS_OPTIONS, param_name="patient class")
        InputValidator.validate_input(patient_age_unit, valid_values=self.VALID_PATIENT_AGE_UNIT_OPTIONS, param_name="patient age unit")
        InputValidator.validate_input(patient_age_from, expected_type=self.VALID_PATIENT_AGE_FROM_TYPE, param_name="patient age from")
        InputValidator.validate_input(patient_age_to, expected_type=self.VALID_PATIENT_AGE_TO_TYPE, param_name="patient age to")
        InputValidator.validate_input(sort, valid_values=self.VALID_SORT_OPTIONS, param_name="sort")


class Report(SoapService):
    NAMESPACE = "http://nuance.com/commissure/webservices/report/2010/06"

    def get_report(self, report_id):
        soap_body = f"""
        <GetReport xmlns="{self.NAMESPACE}">
            <reportID>{report_id}</reportID>
        </GetReport>
        """
        return self.make_soap_request("/services/report.asmx", soap_body)