from src.data_generation.generate_data import generate_all
from src.features.build_longitudinal_features import build_longitudinal_features
from src.modeling.train_longitudinal_model import train
from src.features.build_risk_drivers import build_risk_drivers
from src.optimization.compare_schedules import run as compare_schedules
from src.validation.data_quality import run_quality_checks

def main():
    print("\n[1/6] Generate coherent operational histories")
    generate_all("data/raw")

    print("\n[2/6] Build leakage-controlled asset-month snapshots")
    build_longitudinal_features()

    print("\n[3/6] Train, calibrate, and validate the 30-day risk model")
    train()

    print("\n[4/6] Build transparent operational risk drivers")
    build_risk_drivers()

    print("\n[5/6] Compare rule-based vs optimized maintenance scheduling")
    compare_schedules()

    print("\n[6/6] Run data-quality observability checks")
    run_quality_checks()

    print("\nGRIDWATCH NYC FINAL PIPELINE COMPLETE")
    print("Launch dashboard with: python -m streamlit run app/app.py")

if __name__ == "__main__":
    main()
