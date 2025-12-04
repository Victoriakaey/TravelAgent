import time
import os

class TimingTracker:
    def __init__(self, user_id: str, output_folder: str):
        self.user_id = user_id
        self.output_folder = output_folder
        self.execution_times = {}
        self.start_times = {}

    def start(self, name: str):
        self.start_times[name] = time.perf_counter()

    def stop(self, name: str):
        if name not in self.start_times:
            raise ValueError(f"Timer for '{name}' was never started.")
        duration = time.perf_counter() - self.start_times[name]
        self.execution_times[name] = f"{duration:.2f} seconds"
        return duration

    def log_attempt(self, name: str, duration: float):
        if name not in self.execution_times:
            self.execution_times[name] = []
        self.execution_times[name].append(f"{duration:.2f} seconds")

    def save_as_text(self, filename: str = None):
        if filename is None:
            filename = f"{self.user_id}_timing_log.txt"
        filepath = os.path.join(self.output_folder, filename)

        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "a") as f:
            f.write(f"Execution times for user_id={self.user_id} at {time.ctime()}\n")
            for key, value in self.execution_times.items():
                if isinstance(value, list):
                    for i, v in enumerate(value, 1):
                        f.write(f"{key} attempt {i}: {v}\n")
                else:
                    f.write(f"{key}: {value}\n")
            f.write("-" * 40 + "\n")
        print(f"[TimingTracker] Execution log saved to {filepath}")

    def save_as_markdown(self, filename: str = None):
        if filename is None:
            filename = f"{self.user_id}_timing_log.md"
        filepath = os.path.join(self.output_folder, filename)

        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        lines = ["| Step | Duration |", "|------|----------|"]
        for key, value in self.execution_times.items():
            if isinstance(value, list):
                for i, v in enumerate(value, 1):
                    lines.append(f"| {key} attempt {i} | {v} |")
            else:
                lines.append(f"| {key} | {value} |")
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        print(f"[TimingTracker] Markdown log saved to {filepath}")
