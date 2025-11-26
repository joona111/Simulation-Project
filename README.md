# Surgery Unit Simulation Project

This project simulates the flow of patients through a hospital surgery unit using **discrete-event simulation** with [SimPy](https://simpy.readthedocs.io/).

The simulated system has three main stages:

1. **Preparation** (e.g., anesthesia and pre-op checks)  
2. **Operating Room (OR)** – the actual surgery  
3. **Recovery** – monitored wake-up/recovery area  

Patients arrive over time, occupy resources (prep units, OR, recovery beds), and the simulation records metrics such as:

- Number of patients completed
- Per-patient waiting and total time in the system
- Queue lengths over time (prep, OR, recovery)
- OR utilization over time

---

## Project Structure

```text
Simulation-Project/
├── config.py          # All global simulation parameters + random helpers
├── hospital_model.py  # Core SimPy processes (patient flow + monitoring)
├── run_sim.py         # Entry point to configure and run a simulation
├── Hospital.ipynb     # (Optional) Notebook for analysis/visualization
├── dense.ipynb        # minimalist notebook using alt. versions of functions
|       - only needs hospital_model and config
├── requirements.txt   # Python dependencies
