# 🛠️ CrewSchd - Advanced Crew Scheduling System

CrewSchd is an enterprise-grade shift scheduling system built with Python, Google OR-Tools, and Google Gemini API. It handles complex constraints like Thai Labor Laws, company policies, and dynamic business requirements through a modular math engine.

## 🚀 Features

- **Math Engine**: Powered by Google OR-Tools (CP-SAT Solver) for optimal scheduling.
- **AI Roster Assistant**: Natural language translation using Google Gemini (2.5 Flash) to handle dynamic overrides (e.g., sick leaves, special requests).
- **Interactive Dashboard**: Built with Streamlit for roster visualization, management, and analytics.
- **Thai Labor Law Compliance**: Hard-coded constraints based on the Thai Labor Protection Act.
- **Time Machine**: Roll back to previous roster versions and restore their states.
- **Advanced Analytics**: Monitor workforce health and burnout risks.

## 🛠️ Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/CrewSchd.git
   cd CrewSchd
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   ```
   *Required:* `GEMINI_API_KEY` (Get it from [Google AI Studio](https://aistudio.google.com/)).

5. **Run the Dashboard**:
   ```bash
   streamlit run Dashboard.py
   ```

## 📂 Project Structure

- `Dashboard.py`: Main Streamlit UI.
- `roster_engine.py`: Core CP-SAT solver and orchestration.
- `modules/`: Individual constraint modules (laws, policies, context, etc.).
- `jsons/`: Configuration and data files (employees, rules).
- `run_translation.py`: Helper script to test natural language translation.
- `Exporter.py`: Generates the staff-centric HTML roster report.

## ⚖️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
