import json
import logging
import traceback


class JSONFormatter(logging.Formatter):
    def format(self, record):
        # Field dasar (untuk semua event)
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "level": record.levelname,
            "event": record.msg,
            # "method": getattr(record, "method", None),
            # "path": getattr(record, "path", None),
        }

        event_type = getattr(record, "event_type", None)

        # ---- LOGIN EVENT ----
        if event_type == "login":
            log_record.update(
                {
                    "user_id": getattr(record, "user_id", None),
                    "email": getattr(record, "email", None),
                    "ip_address": getattr(record, "ip_address", None),
                    "user_agent": getattr(record, "user_agent", None),
                }
            )

        # ---- REFRESH TOKEN EVENT ----
        elif event_type == "token_refresh":
            log_record.update(
                {
                    "status": getattr(record, "status", None),
                    "user_id": getattr(record, "user_id", None),
                    "ip_address": getattr(record, "ip_address", None),
                    "user_agent": getattr(record, "user_agent", None),
                }
            )

        elif event_type == "checkout":
            log_record.update(
                {
                    "origin": getattr(record, "origin", None),
                    "destination": getattr(record, "destination", None),
                    "weight": getattr(record, "weight", None),
                    "courier": getattr(record, "courier", None),
                }
            )

        elif event_type == "transaction":
            log_record["order_id"] = getattr(record, "order_id", None)
            
            if hasattr(record, "payload"):
                log_record["payload"] = record.payload
            
            if hasattr(record, "status_code"):
                log_record["status_code"] = record.status_code
            
            if hasattr(record, "transaction_status"):
                log_record["transaction_status"] = record.transaction_status
                
            if hasattr(record, "response"):
                log_record["response"] = record.response
            
            if hasattr(record, "checkout_id"):
                log_record["checkout_id"] = record.checkout_id
            
        return json.dumps(log_record)
