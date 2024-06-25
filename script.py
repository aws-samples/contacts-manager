# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import logging
import time
import os
import re
import openpyxl
import pandas as pd
from simple_term_menu import TerminalMenu
from botocore.exceptions import ClientError
from datetime import datetime
from pprint import pprint

# List all AWS Account IDs in Organizations
def list_accounts_func():
    list_of_accounts_id = []
    try:
        list_accounts = boto3.client('organizations').list_accounts()
        list_of_accounts = list_accounts['Accounts']
        while 'NextToken' in list_accounts:
            list_accounts = boto3.client('organizations').list_accounts(NextToken=list_accounts['NextToken'])
            list_of_accounts += list_accounts['Accounts']
    except ClientError as e:
        print(f'\n Could not list AWS accounts... Error: {str(e)}')
        logging.error(e)
        exit()
    for account in list_of_accounts:
        list_of_accounts_id.append(str(account["Id"]))
    return list_of_accounts_id

# List all AWS Account IDs in Organizations from specific OU
def list_ou_accounts_func(ou_id):
    list_of_accounts_id = []
    try:
        list_accounts = boto3.client('organizations').list_accounts_for_parent(
            ParentId=ou_id
        )
        list_of_accounts = list_accounts['Accounts']
        while 'NextToken' in list_accounts:
            list_accounts = boto3.client('organizations').list_accounts_for_parent(NextToken=list_accounts['NextToken'], ParentId=ou_id)
            list_of_accounts += list_accounts['Accounts']
    except ClientError as e:
        print(f'\n Could not list AWS accounts... Error: {str(e)}')
        logging.error(e)
        exit()
    for account in list_of_accounts:
        list_of_accounts_id.append(str(account["Id"]))
    return list_of_accounts_id

# Captures the AWS Account ID of the logged in account
def get_account_id():
    return boto3.client('sts').get_caller_identity()['Account']

# Validator if the AWS Account ID is valid and is within the Organizations
def validate_accounts(accounts):
    for x in accounts:
        if len(x) != 12:
            print(f'\nAWS account ID {str(x)} is not a valid AWS Account ID.\n')
            return False
        else:
            aws_org_accounts = list_accounts_func()
            if x not in aws_org_accounts:
                print(f'\nAWS account ID {str(x)} does not belong to your Organization.\n')
                return False
            else:
                return True

# List the alternate contact(s)
def alternate_contact_list_func(accounts, current_account_id, menu_entry_2_list):
    resp = {'AlternateContact': {}}
    client = boto3.client('account')

    for x in accounts:
        alternate_contact_type = {}
        for y in menu_entry_2_list:
            print(f'Getting {y} alternate contact for {x}...')
            try:
                if x == current_account_id:
                    resp_alternate_contact = client.get_alternate_contact(AlternateContactType=y.upper())
                else:
                    resp_alternate_contact = client.get_alternate_contact(AccountId=str(x), AlternateContactType=y.upper())
                resp_alternate_contact['AlternateContact'].pop('AlternateContactType')
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    resp_alternate_contact = {}
                    resp_alternate_contact['AlternateContact'] = 'Null'
                else:
                    print('\n')
                    logging.error(e)
                    return False
            alternate_contact_type[y] = resp_alternate_contact['AlternateContact']
        resp['AlternateContact'][x] = alternate_contact_type

    export_to_s3 = input('\nDo you want to export the result to an S3 bucket? (y/N): ')
    if export_to_s3.lower() in ['y', 'yes']:
        s3_bucket_name = input('S3 bucket name: ')
        s3_object_name = 'alternate-contact-list_' + \
            datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + '.json'
        s3_client = boto3.client('s3')
        try:
            s3_client.put_object(
                Body=bytes(json.dumps(resp).encode('UTF-8')),
                Bucket=s3_bucket_name,
                Key=s3_object_name
            )
        except ClientError as e:
            print('\n')
            logging.error(e)
            print(e)
            return False
        return True
    else:
        print('\nReturn: \n')
        pprint(resp['AlternateContact'])
        return True

# Update the alternate contact(s)
def alternate_contact_update_func(accounts, current_account_id, menu_entry_2_list):
    client = boto3.client('account')

    email_address = input(f'Type the email address (E.g. {menu_entry_2_list[0].lower()}.team@email.com): ')
    name = input(f'Type the name (E.g. {menu_entry_2_list[0].capitalize() } Team): ')
    phone_number = input('Type the phone number (E.g. (000) 000-0000): ')
    title = input(f'Type the title (E.g. {menu_entry_2_list[0].capitalize()} Internal Team): ')
    print('')

    for x in accounts:
        for y in menu_entry_2_list:
            print(f'Updating {y} alternate contact for AWS account {x}...')
            if current_account_id == x:
                try:
                    client.put_alternate_contact(
                        AlternateContactType=y.upper(),
                        EmailAddress=email_address,
                        Name=name,
                        PhoneNumber=phone_number,
                        Title=title
                    )
                except ClientError as e:
                    print(f'\n Could not update {y} alternate contact for AWS account {x}... Error: {str(e)}')
                    logging.error(e)
                    return False
            else:
                try:
                    client.put_alternate_contact(
                        AccountId=x,
                        AlternateContactType=y.upper(),
                        EmailAddress=email_address,
                        Name=name,
                        PhoneNumber=phone_number,
                        Title=title
                    )
                except ClientError as e:
                    print(f'\n Could not update {y} alternate contact for AWS account {x}... Error: {str(e)}')
                    logging.error(e)
                    return False
    return True

# Delete the alternate contact(s)
def alternate_contact_delete_func(accounts, current_account_id, menu_entry_2_list):
    client = boto3.client('account')

    for x in accounts:
        for y in menu_entry_2_list:
            print(f'Deleting {y} alternate contact for {x}...')
            if current_account_id == x:
                try:
                    client.delete_alternate_contact(
                        AlternateContactType=y.upper()
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        pass
                    else:
                        print(f'\n Could not delete {y} alternate contact for AWS account {x}... Error: {str(e)}')
                        logging.error(e)
                        return False
            else:
                try:
                    client.delete_alternate_contact(
                        AccountId=x,
                        AlternateContactType=y.upper()
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        pass
                    else:
                        print(f'\n Could not delete {y} alternate contact for AWS account {x}... Error: {str(e)}')
                        logging.error(e)
                        return False
    return True

# List the primary contact information
def primary_contact_list_func(accounts, current_account_id):
    resp = {'PrimaryContactInformation': {}}
    client = boto3.client('account')

    for x in accounts:
        print(f'Getting primary contact information for AWS account {x}...')
        try:
            if x == current_account_id:
                resp_primary_contact_info = client.get_contact_information()
            else:
                resp_primary_contact_info = client.get_contact_information(AccountId=x)
        except ClientError as e:
            print(f'\n Could not list primary contact information for AWS account {x}... Error: {str(e)}')
            logging.error(e)
            exit()
        primary_contact_information = resp_primary_contact_info['ContactInformation']
        resp['PrimaryContactInformation'][x] = primary_contact_information

    export_to_s3 = input('\nDo you want to export the result to an S3 bucket? (y/N): ')
    if export_to_s3.lower() in ['y', 'yes']:
        s3_bucket_name = input('S3 bucket name: ')
        s3_object_name = 'primary-contat-information-list_' + \
            datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + '.json'
        s3_client = boto3.client('s3')
        try:
            s3_client.put_object(
                Body=bytes(json.dumps(resp).encode('UTF-8')),
                Bucket=s3_bucket_name,
                Key=s3_object_name
            )
        except ClientError as e:
            print('\n')
            logging.error(e)
            print(e)
            return False
        return True
    else:
        print('\nReturn: \n')
        pprint(resp['PrimaryContactInformation'])
        return True

# Update the primary contact information
def primary_contact_update_func(accounts, current_account_id):
    client = boto3.client('account')

    required_input = ['AddressLine1', 'City', 'FullName', 'PhoneNumber', 'PostalCode']
    optional_input = ['AddressLine2', 'AddressLine3', 'CompanyName', 'DistrictOrCounty', 'StateOrRegion', 'WebsiteUrl']

    while True:
        validation = True
        remove_input = []
        contact_information = {
            'AddressLine1': '',
            'AddressLine2': '',
            'AddressLine3': '',
            'City': '',
            'CompanyName': '',
            'CountryCode': '',
            'DistrictOrCounty': '',
            'FullName': '',
            'PhoneNumber': '',
            'PostalCode': '',
            'StateOrRegion': '',
            'WebsiteUrl': ''
        }
        contact_information['AddressLine1'] = input('[REQUIRED] Address line 1 (the first line of the primary contact address): ')
        contact_information['AddressLine2'] = input('[OPTIONAL] Address line 2 (the second line of the primary contact address, if any): ')
        contact_information['AddressLine3'] = input('[OPTIONAL] Address line 3 (the third line of the primary contact address, if any): ')
        contact_information['City'] = input('[REQUIRED] City (the city of the primary contact address): ')
        contact_information['CompanyName'] = input('[OPTIONAL] Company name (the name of the company associated with the primary contact information, if any): ')
        contact_information['CountryCode'] = input('[REQUIRED] Country code (the ISO-3166 two-letter country code for the primary contact address): ')
        contact_information['DistrictOrCounty'] = input('[OPTIONAL] District or county (the district or county of the primary contact address, if any): ')
        contact_information['FullName'] = input('[REQUIRED] Full name (the full name of the primary contact address): ')
        contact_information['PhoneNumber'] = input('[REQUIRED] Phone number (the phone number of the primary contact information): ')
        contact_information['PostalCode'] = input('[REQUIRED] Postal code (the postal code of the primary contact address): ')
        contact_information['StateOrRegion'] = input('[OPTIONAL] State or region (the state or region of the primary contact address): ')
        contact_information['WebsiteUrl'] = input('[OPTIONAL] Website URL (the URL of the website associated with the primary contact information, if any): ')
        print('\n')

        for key, value in contact_information.items():
            temp_value = value.replace(" ", "")
            if key in optional_input and temp_value == '':
                remove_input.append(key)
            else:
                pass
            if key in required_input and temp_value == '':
                print(f'Error: The {key} field cannot be empty.')
                validation = False
            else:
                pass

        for y in remove_input:
            del contact_information[y]

        if validation == True:
            break
        else:
            print('\nSome of the required fields were left empty, please fill in the fields again.\n')

    for x in accounts:
        print(f'Updating primary contact information for AWS account {x}...')
        if current_account_id == x:
            try:
                client.put_contact_information(
                    ContactInformation=contact_information
                )
            except ClientError as e:
                print(f'\n Could not update primary contact information for AWS account {x}... Error: {str(e)}')
                logging.error(e)
                return False
        else:
            try:
                client.put_contact_information(
                    AccountId=x,
                    ContactInformation=contact_information
                )
            except ClientError as e:
                print(f'\n Could not update primary contact information for account {x}... Error: {str(e)}')
                logging.error(e)
                return False
    return True

# List the root email
def root_email_list_func(accounts, current_account_id):
    resp = {'RootEmailAddresses': {}}
    client = boto3.client('account')

    for x in accounts:
        print(f'Getting root email address for AWS account {x}...')
        try:
            if x == current_account_id:
                resp_root_email = {'PrimaryEmail': 'management account - not available'}
            else:
                resp_root_email = client.get_primary_email(AccountId=x)
        except ClientError as e:
            print(f'\n Could not list root email address for AWS account {x}... Error: {str(e)}')
            logging.error(e)
            exit()
        root_email_information = resp_root_email['PrimaryEmail']
        resp['RootEmailAddresses'][x] = root_email_information

    export_to_s3 = input('\nDo you want to export the result to an S3 bucket? (y/N): ')
    if export_to_s3.lower() in ['y', 'yes']:
        s3_bucket_name = input('S3 bucket name: ')
        s3_object_name = 'root-email-address-list_' + \
            datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + '.json'
        s3_client = boto3.client('s3')
        try:
            s3_client.put_object(
                Body=bytes(json.dumps(resp).encode('UTF-8')),
                Bucket=s3_bucket_name,
                Key=s3_object_name
            )
        except ClientError as e:
            print('\n')
            logging.error(e)
            print(e)
            return False
        return True
    else:
        print('\nReturn: \n')
        pprint(resp['RootEmailAddresses'])
        return True

# Update the root email(s)
def root_email_update_func(accounts, current_account_id):
    client = boto3.client('account')
    change_status = ['⟳'] * len(accounts)
    accounts.sort()
    regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    green = '\033[92m'
    cyan = '\033[96m'
    italic = '\033[0;3m'
    underline = '\033[4m'
    regular = '\033[0;0m'

    while(True):
        account_change_status = []
        accounts_left = 0
        for x in range(len(accounts)):
            account_change_status.append(str(change_status[x]) + ' - ' + str(accounts[x]))
            if change_status[x] == '⟳':
                accounts_left += 1

        options_5 = account_change_status
        terminal_menu_5 = TerminalMenu(options_5, title=f'Select the AWS account to update the root email ({accounts_left} AWS account(s) left):', menu_cursor_style=('fg_cyan', 'bold'), clear_screen=False)
        menu_entry_index_5 = terminal_menu_5.show()
        menu_entry_5 = options_5[menu_entry_index_5]
        selected_account = menu_entry_5[4:]
        print(f'{italic}{cyan}You have selected to {underline}Update{regular}{italic}{cyan} the root email of the AWS Account {underline}{selected_account}{regular}{italic}{cyan}.{regular}\n')

        while(True):
            new_email = input('Type the new root email address: ')
            if(re.fullmatch(regex, new_email)):
                break
            else:
                print('Invalid email, try it again.')

        if current_account_id == selected_account:
            try:
                client.start_primary_email_update(
                    PrimaryEmail=new_email
                )
            except ClientError as e:
                print(f'\n Could not update  root email AWS account {selected_account}... Error: {str(e)}')
                logging.error(e)
                return False
        else:
            try:
                client.start_primary_email_update(
                    AccountId=selected_account,
                    PrimaryEmail=new_email
                )
            except ClientError as e:
                print(f'\n Could not update  root email AWS account {selected_account}... Error: {str(e)}')
                logging.error(e)
                return False

        while(True):
            otp_code = input(f'\nType the one-time password (OTP) received at {new_email}: ')

            if current_account_id == selected_account:
                try:
                    resp = client.accept_primary_email_update(
                        Otp=otp_code,
                        PrimaryEmail=new_email
                    )
                except ClientError as e:
                    print(f'\n Could not update root email for the AWS account {selected_account}... Error: {str(e)}')
                    logging.error(e)
                    return False
            else:
                try:
                    resp = client.accept_primary_email_update(
                        AccountId=selected_account,
                        Otp=otp_code,
                        PrimaryEmail=new_email
                    )
                except ClientError as e:
                    print(f'\nCould not update root email for the AWS account {selected_account}... Error: {str(e)}')
                    logging.error(e)
                    return False

            if resp['Status'] == 'ACCEPTED':
                for y in range(len(accounts)):
                    if accounts[y] == selected_account:
                        change_status[y] = '✔'
                        print(f'\n{italic}{cyan}New root email updated to {underline}{new_email}{regular}{italic}{cyan} to AWS account {underline}{selected_account}{regular}{italic}{cyan} successfully.{regular}\n')
                break
            else:
                pass

        if '⟳' in change_status:
            pass
        else:
            print(f'{italic}{green}✔ All new root email updated successfully.{regular}')
            break
    return True

# Generate report
def generate_report(current_account_id):
    resp = {}
    report = [['Account ID', 'Account Name', 'Status', 'Root Email Address', 'Phone Number', 'Billing Alternate Contact - Name', 'Billing Alternate Contact - Title', 'Billing Alternate Contact - Email', 'Billing Alternate Contact - Phone Number', 'Operations Alternate Contact - Name', 'Operations Alternate Contact - Title', 'Operations Alternate Contact - Email', 'Operations Alternate Contact - Phone Number', 'Security Alternate Contact - Name', 'Security Alternate Contact - Title', 'Security Alternate Contact - Email', 'Security Alternate Contact - Phone Number']]

    list_of_accounts_id = []
    try:
        list_accounts = boto3.client('organizations').list_accounts()
        list_of_accounts = list_accounts['Accounts']
        while 'NextToken' in list_accounts:
            list_accounts = boto3.client('organizations').list_accounts(NextToken=list_accounts['NextToken'])
            list_of_accounts += list_accounts['Accounts']
    except ClientError as e:
        print(f'\n Could not list AWS accounts... Error: {str(e)}')
        logging.error(e)
        exit()
    for account in list_of_accounts:
        list_of_accounts_id.append(str(account["Id"]))
        resp[account["Id"]] = account

    for x in list_of_accounts_id:
        print(f'Getting information for AWS account {x}...')
        try:
            if x == current_account_id:
                resp_get_contact_information = boto3.client('account').get_contact_information()
            else:
                resp_get_contact_information = boto3.client('account').get_contact_information(AccountId=x)
            resp[x] = resp[x] | resp_get_contact_information['ContactInformation']
        except ClientError as e:
            print(f'\n Could not generate report... Error: {str(e)}')
            logging.error(e)
            exit()
        try:
            if x == current_account_id:
                resp[x] = resp[x] | {'PrimaryEmail': 'management account - not available'}
            else:
                resp_get_primary_email = boto3.client('account').get_primary_email(AccountId=x)
                resp_get_primary_email.pop('ResponseMetadata')
                resp[x] = resp[x] | resp_get_primary_email
        except ClientError as e:
            print(f'\n Could not generate report... Error: {str(e)}')
            logging.error(e)
            exit()
        for y in ['Billing','Operations','Security']:
            try:
                if x == current_account_id:
                    resp_get_primary_email = boto3.client('account').get_alternate_contact(AlternateContactType=y.upper())
                else:
                    resp_get_primary_email = boto3.client('account').get_alternate_contact(AccountId=x, AlternateContactType=y.upper())
                resp[x][f'{y}AlternateContact'] = resp_get_primary_email['AlternateContact']
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    resp[x][f'{y}AlternateContact'] = {'AlternateContactType': 'BILLING', 'EmailAddress': '', 'Name': '', 'PhoneNumber': '', 'Title': ''}
                else:
                    print(f'\n Could not generate report... Error: {str(e)}')
                    logging.error(e)
                    exit()

    for z in resp:
        report_account = []
        report_account.append(resp[z]['Id'])
        report_account.append(resp[z]['Name'])
        report_account.append(resp[z]['Status'])
        report_account.append(resp[z]['PrimaryEmail'])
        report_account.append(resp[z]['PhoneNumber'])
        report_account.append(resp[z]['BillingAlternateContact']['Name'])
        report_account.append(resp[z]['BillingAlternateContact']['Title'])
        report_account.append(resp[z]['BillingAlternateContact']['EmailAddress'])
        report_account.append(resp[z]['BillingAlternateContact']['PhoneNumber'])
        report_account.append(resp[z]['OperationsAlternateContact']['Name'])
        report_account.append(resp[z]['OperationsAlternateContact']['Title'])
        report_account.append(resp[z]['OperationsAlternateContact']['EmailAddress'])
        report_account.append(resp[z]['OperationsAlternateContact']['PhoneNumber'])
        report_account.append(resp[z]['SecurityAlternateContact']['Name'])
        report_account.append(resp[z]['SecurityAlternateContact']['Title'])
        report_account.append(resp[z]['SecurityAlternateContact']['EmailAddress'])
        report_account.append(resp[z]['SecurityAlternateContact']['PhoneNumber'])
        report.append(report_account)

    # Create a new Excel workbook
    workbook = openpyxl.Workbook()
    # Select the default sheet (usually named 'Sheet')
    sheet = workbook.active
    # Add data to the Excel sheet
    data = report
    for row in data:
        sheet.append(row)
    # Save the workbook to a file
    workbook.save(f'aws-contacts-report-{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}.xlsx')

    return True

# Main function
def main():
    while(True):
        bold = '\033[1m'
        italic = '\033[0;3m'
        regular = '\033[0;0m'
        underline = '\033[4m'
        cyan = '\033[96m'
        green = '\033[92m'
        yellow = '\033[33m'
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f'\n{bold}{cyan}Contacts Manager{regular}')
        print(f'{italic}Solution developed for batch management of AWS accounts contacts. For more information, visit: https://github.com/aws-samples/aws-contacts-manager.\n{regular}')

        # First choice menu
        options_0 = ['Alternate contacts', 'Primary contacts information', 'Root email addresses', 'Generate contacts report']
        terminal_menu_0 = TerminalMenu(options_0, title='Choose the contact type or report:', menu_cursor_style=('fg_cyan', 'bold'), clear_screen=False)
        menu_entry_index_0 = terminal_menu_0.show()
        menu_entry_0 = options_0[menu_entry_index_0]
        print(f'{italic}{cyan}You have selected {underline}{menu_entry_0}{regular}{italic}{cyan}!{regular}\n')

        # Get current account id
        current_account_id = get_account_id()

        # Alternate contacts choice
        if menu_entry_0 == 'Alternate contacts':
            options_1 = ['List', 'Update', 'Delete']
            terminal_menu_1 = TerminalMenu(options_1, title='Choose the action:', menu_cursor_style=('fg_cyan', 'bold'), clear_screen=False)
            menu_entry_index_1 = terminal_menu_1.show()
            menu_entry_1 = options_1[menu_entry_index_1]
            print(f'{italic}{cyan}You have selected to {underline}{menu_entry_1}{regular}{italic}{cyan} AWS account(s) {underline}{menu_entry_0}{regular}{italic}{cyan}!{regular}\n')
            if menu_entry_1 == 'Delete':
                accounts = input('AWS account ID (delete action allowed for one AWS account at a time): ')
                accounts = accounts.split(',')
            else:
                accounts = input('AWS account ID(s) (enter a list of AWS account IDs separated by comma / Organizational unit ID / all): ')
                if accounts == 'all':
                    accounts = list_accounts_func()
                elif accounts[:2] in ('ou', 'r-'):
                    accounts = list_ou_accounts_func(accounts)
                else:
                    accounts = accounts.replace(' ', '')
                    accounts = accounts.split(',')

            # Validator if the AWS Account ID is valid and is within the Organizations
            account_check = validate_accounts(accounts)
            if account_check == False:
                exit()
            else:
                print(f'AWS account validation: {bold}{green}\u2713{regular}')

            print(f'Number of individual AWS accounts detected: {len(accounts)}')

            # Alternate contacts type choice menu
            options_2 = ['Billing', 'Operations', 'Security', 'All']
            terminal_menu_2 = TerminalMenu(options_2, title='\nChoose the alternate contact type:', menu_cursor_style=('fg_cyan', 'bold'), clear_screen=False)
            menu_entry_index_2 = terminal_menu_2.show()
            menu_entry_2 = options_2[menu_entry_index_2]
            print(f'Alternate contact type: {menu_entry_2}\n')
            if menu_entry_2 == 'All':
                menu_entry_2_list = ['Billing', 'Operations', 'Security']
            else:
                menu_entry_2_list = [menu_entry_2]

            tic = time.perf_counter()

            if menu_entry_1 == 'List':
                resp = alternate_contact_list_func(accounts, current_account_id, menu_entry_2_list)
            elif menu_entry_1 == 'Update':
                resp = alternate_contact_update_func(accounts, current_account_id, menu_entry_2_list)
            else:
                resp = alternate_contact_delete_func(accounts, current_account_id, menu_entry_2_list)

            toc = time.perf_counter()

            print(f'\nCompleted successfully in {toc - tic:0.4f} seconds!\n') if resp == True else print('\nERROR: somethig went wrong.\n')

        # Primary contacts information choice
        elif menu_entry_0 == 'Primary contacts information':
            options_3 = ['List', 'Update']
            terminal_menu_3 = TerminalMenu(options_3, title='Choose the action:', menu_cursor_style=('fg_cyan', 'bold'), clear_screen=False)
            menu_entry_index_3 = terminal_menu_3.show()
            menu_entry_3 = options_3[menu_entry_index_3]
            print(f'{italic}{cyan}You have selected to {underline}{menu_entry_3}{regular}{italic}{cyan} AWS account(s) {underline}{menu_entry_0}{regular}{italic}{cyan}!{regular}\n')
            accounts = input('AWS account ID(s) (enter a list of AWS account IDs separated by comma / Organizational unit ID / all): ')
            if accounts == 'all':
                accounts = list_accounts_func()
            elif accounts[:2] in ('ou', 'r-'):
                accounts = list_ou_accounts_func(accounts)
            else:
                accounts = accounts.replace(' ', '')
                accounts = accounts.split(',')

            # Validator if the AWS Account ID is valid and is within the Organizations
            account_check = validate_accounts(accounts)
            if account_check == False:
                exit()
            else:
                print(f'AWS account validation: {bold}{green}\u2713{regular}')

            accounts = list(set(accounts))
            print(f'Number of individual AWS accounts detected: {len(accounts)}\n')

            tic = time.perf_counter()

            if menu_entry_3 == 'List':
                resp = primary_contact_list_func(accounts, current_account_id)
            else:
                resp = primary_contact_update_func(accounts, current_account_id)

            toc = time.perf_counter()

            print(f'\nCompleted successfully in {toc - tic:0.4f} seconds!\n') if resp == True else print('\nERROR: somethig went wrong.\n')

        # Root email addresses choice
        elif menu_entry_0 == 'Root email addresses':
            options_4 = ['List', 'Update']
            terminal_menu_4 = TerminalMenu(options_4, title='Choose the action:', menu_cursor_style=('fg_cyan', 'bold'), clear_screen=False)
            menu_entry_index_4 = terminal_menu_4.show()
            menu_entry_4 = options_4[menu_entry_index_4]
            print(f'{italic}{cyan}You have selected to {underline}{menu_entry_4}{regular}{italic}{cyan} AWS account(s) {underline}{menu_entry_0}{regular}{italic}{cyan}!{regular}\n')

            if menu_entry_4 == 'List':
                print(f'{bold}{yellow}Note: {regular}{yellow}the management account is not supported. If added, value will be "management account - not available".{regular}\n')
                accounts = input('AWS account ID(s) (enter a list of AWS account IDs separated by comma / Organizational unit ID / all): ')
                if accounts == 'all':
                    accounts = list_accounts_func()
                elif accounts[:2] in ('ou', 'r-'):
                    accounts = list_ou_accounts_func(accounts)
                else:
                    accounts = accounts.replace(' ', '')
                    accounts = accounts.split(',')

                # Validator if the AWS Account ID is valid and is within the Organizations
                account_check = validate_accounts(accounts)
                if account_check == False:
                    exit()
                else:
                    print(f'AWS account validation: {bold}{green}\u2713{regular}')

                accounts = list(set(accounts))
                print(f'Number of individual AWS accounts detected: {len(accounts)}\n')

                tic = time.perf_counter()

                resp = root_email_list_func(accounts, current_account_id)

                toc = time.perf_counter()

                print(f'\nCompleted successfully in {toc - tic:0.4f} seconds!\n') if resp == True else print('\nERROR: somethig went wrong.\n')

            else:
                print(f'{bold}{yellow}Note: {regular}{yellow}For security reasons and better experience, only 15 AWS accounts are allowed at a time.\n{regular}')
                accounts = input('AWS account ID(s) (enter a list of AWS account IDs separated by comma / Organizational unit ID / all): ')
                if accounts == 'all':
                    accounts = list_accounts_func()
                elif accounts[:2] in ('ou', 'r-'):
                    accounts = list_ou_accounts_func(accounts)
                else:
                    accounts = accounts.replace(' ', '')
                    accounts = accounts.split(',')

                # Validator if the AWS Account ID is valid and is within the Organizations
                account_check = validate_accounts(accounts)
                if account_check == False:
                    exit()
                else:
                    print(f'AWS account validation: {bold}{green}\u2713{regular}')

                accounts = list(set(accounts))
                print(f'Number of individual AWS accounts detected: {len(accounts)}\n')

                if len(accounts) > 15:
                    print('Error: there are more than 15 AWS accounts selected, please segment into groups of up to 15 AWS accounts to continue.')
                else:
                    tic = time.perf_counter()

                    resp = root_email_update_func(accounts, current_account_id)

                    toc = time.perf_counter()

                    print(f'\nCompleted successfully in {toc - tic:0.4f} seconds!\n') if resp == True else print('\nERROR: somethig went wrong.\n')
        # Generate contacts report
        else:
            print(f'{bold}{yellow}Note: {regular}{yellow}the management account is not supported to get root email address, value will be "management account - not available".{regular}\n')
            tic = time.perf_counter()

            resp = generate_report(current_account_id)

            toc = time.perf_counter()

            print(f'\nCompleted successfully in {toc - tic:0.4f} seconds!\n') if resp == True else print('\nERROR: somethig went wrong.\n')

        resp_end = input('Would you like to run the AWS Contats Manager tool again? (y/N): ')
        if resp_end.lower() in ('y', 'yes'):
            pass
        else:
            break

if __name__ == '__main__':
    main()