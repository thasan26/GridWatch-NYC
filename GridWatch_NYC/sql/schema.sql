-- GridWatch NYC analytical schema (PostgreSQL-style DDL)

CREATE TABLE dim_asset (
    asset_id VARCHAR(20) PRIMARY KEY,
    asset_type VARCHAR(50) NOT NULL,
    borough VARCHAR(30) NOT NULL,
    install_year INT NOT NULL,
    age_years INT NOT NULL,
    criticality INT NOT NULL CHECK (criticality BETWEEN 1 AND 5),
    base_condition DECIMAL(5,2) NOT NULL CHECK (base_condition BETWEEN 0 AND 100),
    required_skill VARCHAR(30) NOT NULL
);

CREATE TABLE fact_inspection (
    asset_id VARCHAR(20) NOT NULL REFERENCES dim_asset(asset_id),
    inspection_date DATE NOT NULL,
    condition_score DECIMAL(5,2) NOT NULL CHECK (condition_score BETWEEN 0 AND 100),
    condition_band VARCHAR(20) NOT NULL,
    PRIMARY KEY (asset_id, inspection_date)
);

CREATE TABLE fact_incident (
    incident_id VARCHAR(20) PRIMARY KEY,
    asset_id VARCHAR(20) NOT NULL REFERENCES dim_asset(asset_id),
    incident_date DATE NOT NULL,
    severity VARCHAR(20) NOT NULL,
    downtime_hours DECIMAL(8,2) NOT NULL CHECK (downtime_hours >= 0),
    incident_type VARCHAR(100) NOT NULL
);

CREATE TABLE fact_work_order (
    work_order_id VARCHAR(20) PRIMARY KEY,
    asset_id VARCHAR(20) NOT NULL REFERENCES dim_asset(asset_id),
    work_type VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    created_date DATE NOT NULL,
    sla_due_date DATE NOT NULL,
    completed_date DATE,
    status VARCHAR(20) NOT NULL,
    estimated_hours DECIMAL(8,2) NOT NULL CHECK (estimated_hours > 0),
    required_skill VARCHAR(30) NOT NULL,
    CHECK (sla_due_date >= created_date),
    CHECK (completed_date IS NULL OR completed_date >= created_date)
);

CREATE TABLE dim_technician (
    technician_id VARCHAR(20) PRIMARY KEY,
    primary_skill VARCHAR(30) NOT NULL,
    secondary_skill VARCHAR(30) NOT NULL,
    available_hours DECIMAL(6,2) NOT NULL CHECK (available_hours > 0)
);

CREATE INDEX idx_incident_asset_date ON fact_incident(asset_id, incident_date);
CREATE INDEX idx_work_order_asset_date ON fact_work_order(asset_id, created_date);
CREATE INDEX idx_work_order_status_sla ON fact_work_order(status, sla_due_date);
CREATE INDEX idx_inspection_asset_date ON fact_inspection(asset_id, inspection_date);
