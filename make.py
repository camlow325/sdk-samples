'''
This is the NCOS SDK tool used to created applications
for Cradlepoint NCOS devices. It will work on Linux,
OS X, and Windows once the computer environment is setup.
'''

import os
import sys
import uuid
import json
import shutil
import requests
import subprocess
import configparser

from requests.auth import HTTPDigestAuth

# These will be set in init() by using the sdk_settings.ini file.
# They are used by various functions in the file.
g_app_name = ''
g_app_uuid = ''
g_dev_client_ip = ''
g_dev_client_username = ''
g_dev_client_password = ''
g_python_cmd = 'python3'  # Default for Linux and OS X


# Returns an HTTPDigestAuth for the global username and password.
def get_digest():
    return HTTPDigestAuth(g_dev_client_username, g_dev_client_password)


# Returns boolean to indicate if the NCOS device is
# in DEV mode
def is_NCOS_device_in_DEV_mode():
    sdk_status = json.loads(get('/status/system/sdk')).get('data')
    if sdk_status.get('mode') == 'devmode':
        return True
    else:
        return False


# Returns the app package name based on the global app name.
def get_app_pack():
    package_name = g_app_name + ".tar.gz"
    return package_name


# Gets data from the NCOS config store
def get(config_tree):
    ncos_api = 'http://{}/api/{}'.format(g_dev_client_ip, config_tree)

    try:
        response = requests.get(ncos_api, auth=get_digest())

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as ex:
        print("Error with get for NCOS device at {}. Exception: {}".format(g_dev_client_ip, ex))
        return None

    return json.dumps(json.loads(response.text), indent=4)


# Puts an SDK action in the NCOS device config store
def put(value):
    try:
        response = requests.put("http://{}/api/control/system/sdk/action".format(g_dev_client_ip),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                auth=get_digest(),
                                data={"data": '"{} {}"'.format(value, get_app_uuid())})

        print('status_code: {}'.format(response.status_code))

    except (requests.exceptions.Timeout,
            requests.exceptions.ConnectionError) as ex:
        print("Error with put for NCOS device at {}. Exception: {}".format(g_dev_client_ip, ex))
        return None

    return json.dumps(json.loads(response.text), indent=4)


# Cleans the SDK directory for a given app by removing files created during packaging.
def clean():
    print("Cleaning {}".format(g_app_name))
    app_pack_name = get_app_pack()
    try:
        files_to_clean = [g_app_name + ".tar.gz", g_app_name + ".tar"]
        for file_name in files_to_clean:
            if os.path.isfile(file_name):
                os.remove(file_name)
                print('Deleted file: {}'.format(file_name))
    except OSError as e:
        print('Clean Error 1 for file {}: {}'.format(app_pack_name, e))

    meta_dir = '{}/{}/METADATA'.format(os.getcwd(), g_app_name)
    try:
        if os.path.isdir(meta_dir):
            shutil.rmtree(meta_dir)
    except OSError as e:
        print('Clean Error 2 for directory {}: {}'.format(meta_dir, e))

    build_file = os.path.join(os.getcwd(), '.build')
    try:
        if os.path.isfile(build_file):
            os.remove(build_file)
    except OSError as e:
        print('Clean Error 3 for file {}: {}'.format(build_file, e))


# Build, just validates, the application code and package.
def build():
    print("Building {}".format(g_app_name))
    success = True
    validate_script_path = os.path.join('tools', 'bin', 'validate_application.py')
    app_path = os.path.join(g_app_name)
    try:
        if sys.platform == 'win32':
            subprocess.check_output('{} {} {}'.format(g_python_cmd, validate_script_path, app_path))
        else:
            subprocess.check_output('{} {} {}'.format(g_python_cmd, validate_script_path, app_path), shell=True)

    except subprocess.CalledProcessError as err:
        print('Error building {}: {}'.format(g_app_name, err))
        success = False
    finally:
        return success


# Package the app files into a tar.gz archive.
def package():
    success = True
    print("Packaging {}".format(g_app_name))
    package_dir = os.path.join('tools', 'bin')
    package_script_path = os.path.join('tools', 'bin', 'package_application.py')
    app_path = os.path.join(g_app_name)

    try:
        subprocess.check_output('{} {} {}'.format(g_python_cmd, package_script_path, app_path), shell=True)
    except subprocess.CalledProcessError as err:
        print('Error packaging {}: {}'.format(g_app_name, err))
        success = False
    finally:
        return success


# Get the SDK status from the NCOS device
def status():
    status_tree = '/status/system/sdk'
    print('Get {} status for NCOS device at {}'.format(status_tree, g_dev_client_ip))
    response = get(status_tree)
    print(response)


# Transfer the app app tar.gz package to the NCOS device
def install():
    if is_NCOS_device_in_DEV_mode():
        app_archive = get_app_pack()

        # Use scp for Linux or OS X
        cmd = 'scp {0} {1}@{2}:/app_upload'.format(app_archive, g_dev_client_username, g_dev_client_ip)

        # For Windows, use pscp.exe in the tools directory
        if sys.platform == 'win32':
            cmd = "./tools/bin/pscp.exe -pw {0} -v {1} {2}@{3}:/app_upload".format(
                   g_dev_client_password, app_archive,
                   g_dev_client_username, g_dev_client_ip)

        print('Installing {} in NCOS device {}.'.format(app_archive, g_dev_client_ip))
        try:
            if sys.platform == 'win32':
                subprocess.check_output(cmd)
            else:
                subprocess.check_output(cmd, shell=True)
        except subprocess.CalledProcessError as err:
            # There is always an error because the NCOS device will drop the connection.
            # print('Error installing: {}'.format(err))
            return 0
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to install the app into {}.'.format(g_dev_client_ip))


# Start the app in the NCOS device
def start():
    if is_NCOS_device_in_DEV_mode():
        print('Start application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('start')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to start the app from {}.'.format(g_dev_client_ip))


# Stop the app in the NCOS device
def stop():
    if is_NCOS_device_in_DEV_mode():
        print('Stop application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('stop')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to stop the app from {}.'.format(g_dev_client_ip))


# Uninstall the app from the NCOS device
def uninstall():
    if is_NCOS_device_in_DEV_mode():
        print('Uninstall application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('uninstall')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to uninstall the app from {}.'.format(g_dev_client_ip))


# Purge the app from the NCOS device
def purge():
    if is_NCOS_device_in_DEV_mode():
        print('Purged application {} for NCOS device at {}'.format(g_app_name, g_dev_client_ip))
        print('Application UUID is {}.'.format(g_app_uuid))
        response = put('purge')
        print(response)
    else:
        print('ERROR: NCOS device is not in DEV Mode! Unable to purge the app from {}.'.format(g_dev_client_ip))


# Prints the help information
def output_help():
    print('Command format is: {} make.py <action>'.format(g_python_cmd))
    print('clean: Clean all project artifacts.\n')
    print('build or package: Create the app archive tar.gz file.\n')
    print('status: Fetch and print current app status from the locally connected NCOS device.\n')
    print('install: Secure copy the app archive to a locally connected NCOS device.')
    print('         The NCOS device must already be in SDK DEV mode via registration ')
    print('         and licensing in NCM.\n')
    print('start: Start the app on the locally connected NCOS device.\n')
    print('stop: Stop the app on the locally connected NCOS device.\n')
    print('uninstall: Uninstall the app from the locally connected NCOS device.\n')
    print('purge: Purge all apps from the locally connected NCOS device.\n')
    print('uuid: Create a UUID for the app and save it to the package.ini file.\n')
    print('help: Print this help information.\n')


# Create a UUID for the application. If one exist, a new one
# is created.
def create_uuid():
    global g_app_uuid

    uuid_key = 'uuid'
    app_config_file = os.path.join(g_app_name, 'package.ini')
    config = configparser.ConfigParser()
    config.read(app_config_file)
    if g_app_name in config:
        if uuid_key in config[g_app_name]:
            g_app_uuid = config[g_app_name][uuid_key]

            _uuid = str(uuid.uuid4())
            config.set(g_app_name, uuid_key, _uuid)
            with open(app_config_file, 'w') as configfile:
                config.write(configfile)
            print('INFO: Created and saved uuid {} in {}'.format(_uuid, app_config_file))
        else:
            print('ERROR: The uuid key does not exist in {}'.format(app_config_file))
    else:
        print('ERROR: The APP_NAME section does not exist in {}'.format(app_config_file))


# Get the uuid from application package.ini if not already set
def get_app_uuid():
    global g_app_uuid

    if g_app_uuid == '':
        uuid_key = 'uuid'
        app_config_file = os.path.join(g_app_name, 'package.ini')
        config = configparser.ConfigParser()
        config.read(app_config_file)
        if g_app_name in config:
            if uuid_key in config[g_app_name]:
                g_app_uuid = config[g_app_name][uuid_key]

                if g_app_uuid == '':
                    # Create a UUID if it does not exist
                    _uuid = str(uuid.uuid4())
                    config.set(g_app_name, uuid_key, _uuid)
                    with open(app_config_file, 'w') as configfile:
                        config.write(configfile)
                    print('INFO: The uuid did not exist in {}'.format(app_config_file))
                    print('INFO: Created and saved uuid {} in {}'.format(_uuid, app_config_file))
            else:
                print('ERROR: The uuid key does not exist in {}'.format(app_config_file))
        else:
            print('ERROR: The APP_NAME section does not exist in {}'.format(app_config_file))

    return g_app_uuid


# Setup all the globals based on the OS and the sdk_settings.ini file.
def init():
    global g_python_cmd
    global g_app_name
    global g_dev_client_ip
    global g_dev_client_username
    global g_dev_client_password

    success = True

    # Keys in sdk_settings.ini
    sdk_key = 'sdk'
    app_key = 'app_name'
    ip_key = 'dev_client_ip'
    username_key = 'dev_client_username'
    password_key = 'dev_client_password'

    if sys.platform == 'win32':
        g_python_cmd = 'python'

    elif sys.platform == 'Darwin':
        # This will exclude the '._' files  in the
        # tar.gz package for OS X.
        os.environ["COPYFILE_DISABLE"] = "1"

    settings_file = os.path.join(os.getcwd(), 'sdk_settings.ini')
    config = configparser.ConfigParser()
    config.read(settings_file)

    # Initialize the globals based on the sdk_settings.ini contents.
    if sdk_key in config:
        if app_key in config[sdk_key]:
            g_app_name = config[sdk_key][app_key]
        else:
            success = False
            print('ERROR 1: The {} key does not exist in {}'.format(app_key, settings_file))

        if ip_key in config[sdk_key]:
            g_dev_client_ip = config[sdk_key][ip_key]
        else:
            success = False
            print('ERROR 2: The {} key does not exist in {}'.format(ip_key, settings_file))

        if username_key in config[sdk_key]:
            g_dev_client_username = config[sdk_key][username_key]
        else:
            success = False
            print('ERROR 3: The {} key does not exist in {}'.format(username_key, settings_file))

        if password_key in config[sdk_key]:
            g_dev_client_password = config[sdk_key][password_key]
        else:
            success = False
            print('ERROR 4: The {} key does not exist in {}'.format(password_key, settings_file))
    else:
        success = False
        print('ERROR 5: The {} section does not exist in {}'.format(sdk_key, settings_file))

    # This will also create a UUID if needed.
    get_app_uuid()

    return success


if __name__ == "__main__":
    # Default is no arguments given.
    if len(sys.argv) < 2:
        output_help()
        sys.exit(0)

    utility_name = str(sys.argv[1]).lower()

    if not init():
        sys.exit(0)

    if utility_name == 'clean':
        clean()

    elif utility_name == 'build':
        # build()
        package()

    elif utility_name == 'package':
        package()

    elif utility_name == 'status':
        status()

    elif utility_name == 'install':
        install()

    elif utility_name == 'start':
        start()

    elif utility_name == 'stop':
        stop()

    elif utility_name == 'uninstall':
        uninstall()

    elif utility_name == 'purge':
        purge()

    elif utility_name == 'uuid':
        create_uuid()

    else:
        output_help()

    sys.exit(0)
