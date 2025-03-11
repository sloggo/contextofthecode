import subprocess
import re
import platform
from src.utils.logging_config import get_logger

logger = get_logger('utils.system_info')

def get_system_info():
    """Get the system UUID and name which are unique to each PC."""
    try:
        # Get computer name using platform module
        name = platform.node()
        
        # Get system UUID using PowerShell
        uuid_cmd = 'powershell -Command "(Get-WmiObject -Class Win32_ComputerSystemProduct).UUID"'
        uuid_output = subprocess.check_output(uuid_cmd, shell=True).decode().strip()
        
        if uuid_output:
            logger.info(f"Retrieved system info - UUID: {uuid_output}, Name: {name}")
            return {
                'uuid': uuid_output,
                'name': name
            }
        else:
            logger.error("Could not find system UUID")
            return None
            
    except Exception as e:
        logger.error(f"Error getting system information: {str(e)}")
        return None

def get_system_uuid():
    """Get the system UUID (System Management BIOS UUID) which is unique to each PC."""
    info = get_system_info()
    return info['uuid'] if info else None 