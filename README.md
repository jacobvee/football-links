# Football Player Connections

This project analyzes football player connections based on shared team experience. It creates a graph database where:
- Nodes represent players
- Edges connect players who played together in the same team and season

## Features

- Find the shortest connection path between any two players
- Search for players in the database
- Automatically saves the graph for faster future loading
- Memory-efficient processing of large datasets

## Requirements

- Python 3.6 or higher
- Pandas and NetworkX libraries

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Make sure your data file `squads_cleaned.csv` is in the same directory as the script.

## Usage

### Basic Usage

Run the script:
```
python player_connections.py
```

The first run will take some time as it processes the CSV file and builds the graph. After that, the graph will be saved and loaded much faster on subsequent runs.

### Command Line Options

```
python player_connections.py [OPTIONS]
```

Available options:
- `--sample SIZE`: Use a smaller sample size for testing (e.g., `--sample 10000`)
- `--rebuild`: Force rebuilding the graph even if it exists
- `--csv FILENAME`: Specify a different CSV file to use (default: 'squads_cleaned.csv')

### Example for Testing

To quickly test with a smaller dataset:
```
python player_connections.py --sample 100000
```

### Interactive Commands

Once running, the script provides an interactive menu:
1. Find connection between two players
2. List all players
3. Exit

### Examples

Finding the connection between Bukayo Saka and Jeremy Frimpong might show:
```
Shortest path from Bukayo Saka to Jeremy Frimpong (2 links):
Bukayo Saka → Granit Xhaka → Jeremy Frimpong
```

## Data Structure

The script expects a CSV file with at least these columns:
- Name: Player's name
- team: Team identifier
- Season: Season identifier (e.g., "2023-2024")

## Performance Notes

- For very large datasets, the initial graph building may take several minutes
- The script processes the CSV file in chunks to manage memory efficiently
- After the first run, the graph is saved to a file for faster loading in future runs 