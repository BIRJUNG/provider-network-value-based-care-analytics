# Custom Data Guide

Run:

```powershell
python scripts\run_provider_network_pipeline.py --custom-provider-utilization data\raw\custom_provider_utilization_template.csv
```

Recommended columns:

```text
provider_id,provider_name,specialty_group,provider_type,state_code,market,beneficiary_count,service_count,medicare_payment_amount,allowed_amount,quality_score,readmission_rate
```
