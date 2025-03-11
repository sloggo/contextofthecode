from flask import Blueprint, redirect, url_for
import logging
from ...utils.logging_config import setup_logger

logger = setup_logger('stocks')

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route('/stocks', methods=['GET'])
def stocks_page():
    """Redirect to the dashboard"""
    return redirect(url_for('views.dashboard'))
