import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


class PriceOracle:
    def __init__(
        self,
        container_name="counter-src",
        base_price=10.0,
        interval=3,
        output_file="price_history.json",
    ):
        self.container_name = container_name
        self.base_price = base_price
        self.interval = interval
        self.output_file = Path(output_file)
        self.history = []

    def get_container_metrics(self):
        """Read resource usage for one Podman container."""

        result = subprocess.run(
            [
                "sudo",
                "podman",
                "stats",
                "--no-stream",
                "--format",
                "json",
                self.container_name,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)

        if isinstance(data, dict):
            data = [data]

        if not data:
            raise RuntimeError("No container statistics returned.")

        stats = data[0]

        cpu_text = str(stats.get("CPU", "0%")).strip()
        memory_text = str(stats.get("MemPerc", "0%")).strip()

        cpu_percent = float(cpu_text.rstrip("%"))
        memory_percent = float(memory_text.rstrip("%"))

        # Podman's CPU percentage is normalized according to
        # its runtime/platform reporting. Keep the value as reported.
        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory_percent, 2),
            "network_mbps": None,
        }

    def calculate_simulated_price(self, cpu, ram):
        utilization = (
            0.6 * (cpu / 100.0)
            + 0.4 * (ram / 100.0)
        )

        price = self.base_price * (
            1.0 + 0.9 * utilization
        )

        return round(price, 3)

    def generate_sample(self):
        metrics = self.get_container_metrics()

        price = self.calculate_simulated_price(
            metrics["cpu_percent"],
            metrics["memory_percent"],
        )

        sample = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "container": self.container_name,
            "cpu_percent": metrics["cpu_percent"],
            "memory_percent": metrics["memory_percent"],
            "network_mbps": metrics["network_mbps"],
            "simulated_price_per_hour": price,
        }

        self.history.append(sample)
        return sample

    def save_history(self):
        existing = []

        if self.output_file.exists():
            try:
                existing = json.loads(
                    self.output_file.read_text()
                )
            except (json.JSONDecodeError, OSError):
                existing = []

        existing.extend(self.history)

        self.output_file.parent.mkdir(
            parents=True, exist_ok=True
        )

        self.output_file.write_text(
            json.dumps(existing, indent=4)
        )

        self.history.clear()

    def run(self):
        print("Container Price Oracle")
        print(f"Container: {self.container_name}")
        print(f"Base price: ${self.base_price:.2f}/hour")
        print(f"Interval: {self.interval} seconds")
        print("Press Ctrl+C to stop.\n")

        try:
            while True:
                sample = self.generate_sample()

                print("=" * 55)
                print(f"Time       : {sample['timestamp']}")
                print(f"Container  : {sample['container']}")
                print(f"CPU        : {sample['cpu_percent']:.2f}%")
                print(
                    f"Memory     : "
                    f"{sample['memory_percent']:.2f}%"
                )
                print("Network    : Not measured yet")
                print(
                    f"Price      : "
                    f"${sample['simulated_price_per_hour']:.3f}/hour"
                )
                print("=" * 55)

                self.save_history()
                time.sleep(self.interval)

        except KeyboardInterrupt:
            self.save_history()
            print("\nPrice Oracle stopped.")
            print(f"History saved to {self.output_file}")


if __name__ == "__main__":
    oracle = PriceOracle(
        container_name="counter-src",
        base_price=10.0,
        interval=3,
        output_file="price_history.json",
    )

    oracle.run()
