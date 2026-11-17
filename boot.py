import esp32

try:
    esp32.Partition.mark_app_valid_cancel_rollback()
except:
    pass

