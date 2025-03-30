import pandas as pd
import networkx as nx
from pathlib import Path
import argparse
import json

def build_graph(csv_file='squads_cleaned.csv', sample_size=None):
    """
    Build a graph of player connections based on shared teams
    
    Args:
        csv_file: Path to the CSV file
        sample_size: If provided, limit to this many rows (for testing)
    """
    print("Loading data...")
    # Load the CSV file with chunks to manage memory better
    if sample_size:
        # Use a smaller sample for testing
        df = pd.read_csv(csv_file, nrows=sample_size)
        print(f"Using sample of {sample_size} rows for testing")
    else:
        # Process the file in chunks to manage memory better
        chunks = []
        chunksize = 100000  # Adjust based on available memory
        
        for chunk in pd.read_csv(csv_file, chunksize=chunksize):
            # Check column names in first chunk
            if len(chunks) == 0:
                print("Available columns:", chunk.columns.tolist())
            
            # Use enhanced_player_id instead of uuid
            chunk = chunk.dropna(subset=['Name', 'team', 'enhanced_player_id'])
            
            # Keep needed columns
            columns_to_keep = ['Name', 'team', 'Season', 'LeagueName', 'enhanced_player_id']
            if 'club_id' in chunk.columns:
                columns_to_keep.append('club_id')
            
            chunks.append(chunk[columns_to_keep])
            
        df = pd.concat(chunks)
        print(f"Loaded {len(df)} rows from {csv_file}")
    
    # Clean up the data
    print("Cleaning data...")
    df = df.dropna(subset=['Name', 'team', 'enhanced_player_id'])
    
    # Remove any rows where Name is a column header mistakenly included in the data
    header_patterns = ['name', 'player', 'position']  # Common header patterns to exclude
    
    # Function to check if a string might be a header
    def is_likely_header(s):
        if not isinstance(s, str):
            return False
        s_lower = s.lower()
        if s_lower in header_patterns:
            return True
        # Check if the name is unrealistically short (likely a header or error)
        if len(s.strip()) <= 1:
            return True
        return False
    
    # Filter out likely headers
    df = df[~df['Name'].apply(is_likely_header)]
    
    # Create a graph
    print("Building graph...")
    G = nx.Graph()
    
    # Dictionary to store connection details (which team and season players were together)
    connection_details = {}
    
    # Dictionary to map player IDs to player names for node labels
    player_id_to_name = {}
    
    # Group players by team and season to create connections
    # Use club_id for team identification
    if 'club_id' in df.columns:
        print("Using club_id for team identification")
        team_seasons = df.groupby(['club_id', 'Season'])
        team_id_field = 'club_id'
    else:
        print("Using team name for team identification")
        team_seasons = df.groupby(['team', 'Season'])
        team_id_field = 'team'
    
    # Add edges between players who played in the same team in the same season
    edge_count = 0
    for (team_id, season), players in team_seasons:
        # Get a list of player IDs and names
        player_data = players[['enhanced_player_id', 'Name']].drop_duplicates().dropna()
        
        # Get team display name
        team_display = team_id
        if team_id_field == 'club_id' and 'team' in players.columns:
            team_names = players['team'].dropna().unique()
            if len(team_names) > 0:
                team_display = team_names[0]
        
        # Include league name for better context if available
        if 'LeagueName' in players.columns:
            league_names = players['LeagueName'].dropna().unique()
            if len(league_names) > 0:
                team_display = f"{team_display} ({league_names[0]})"
        
        # Update player_id to name mapping
        for _, row in player_data.iterrows():
            player_id = row['enhanced_player_id']
            name = row['Name']
            if player_id not in player_id_to_name and isinstance(name, str) and name.strip():
                player_id_to_name[player_id] = name
                # Add node with both ID and display name
                G.add_node(player_id, name=name)
        
        # Get list of unique player IDs for this team-season
        player_ids = player_data['enhanced_player_id'].dropna().unique().tolist()
        
        # Create edges between all pairs of players in this team-season
        for i in range(len(player_ids)):
            id1 = player_ids[i]
            if not isinstance(id1, str) and not isinstance(id1, int):
                continue
            
            for j in range(i + 1, len(player_ids)):
                id2 = player_ids[j]
                if not isinstance(id2, str) and not isinstance(id2, int):
                    continue
                
                G.add_edge(id1, id2)
                
                # Store details of when and where these players were together
                player_pair = tuple(sorted([str(id1), str(id2)]))  # Sort and convert to string for consistent key
                if player_pair not in connection_details:
                    connection_details[player_pair] = []
                
                # Store as a JSON-compatible formatted string
                connection_info = f"{season}|{team_display}"
                if connection_info not in connection_details[player_pair]:
                    connection_details[player_pair].append(connection_info)
                
                edge_count += 1
                if edge_count % 100000 == 0:
                    print(f"Added {edge_count} connections...")
    
    print(f"Graph built with {G.number_of_nodes()} players and {G.number_of_edges()} connections")
    
    # Store connection details as graph attribute - as a string attribute
    for u, v in G.edges():
        player_pair = tuple(sorted([str(u), str(v)]))
        details = connection_details.get(player_pair, [])
        # Store as a JSON string to ensure GML compatibility
        G[u][v]['details'] = json.dumps(details)
    
    # Store the player_id_to_name mapping as a graph attribute
    nx.set_node_attributes(G, player_id_to_name, 'name')
    
    return G

def get_path_details(G, path):
    """Get details for each connection in a path"""
    path_details = []
    for i in range(len(path)-1):
        p1, p2 = path[i], path[i+1]
        
        # Get player names from node attributes
        p1_name = G.nodes[p1].get('name', p1)
        p2_name = G.nodes[p2].get('name', p2)
        
        # Get the edge data for this connection
        edge_data = G.get_edge_data(p1, p2)
        
        # Parse the JSON string back into a list
        try:
            connection_info_str = edge_data.get('details', '[]')
            connection_info = json.loads(connection_info_str)
        except (json.JSONDecodeError, TypeError):
            connection_info = []
            
        # Parse each connection string back into season and team
        parsed_connections = []
        for conn in connection_info:
            try:
                season, team = conn.split('|', 1)
                parsed_connections.append((season, team))
            except (ValueError, AttributeError):
                continue
                
        path_details.append((p1_name, p2_name, parsed_connections))
    
    return path_details

def get_player_id(G, player_name):
    """Find a player's ID by name"""
    # First try exact match
    for node, attrs in G.nodes(data=True):
        if attrs.get('name') == player_name:
            return node
    
    # If no exact match, try case-insensitive match
    player_lower = player_name.lower()
    matches = []
    for node, attrs in G.nodes(data=True):
        name = attrs.get('name', '')
        if isinstance(name, str) and name.lower() == player_lower:
            matches.append((node, name))
    
    if len(matches) == 1:
        return matches[0][0]
    elif len(matches) > 1:
        print(f"Multiple players found with name '{player_name}':")
        for i, (player_id, name) in enumerate(matches, 1):
            print(f"{i}. {name} (ID: {player_id})")
        try:
            choice = int(input("Enter the number of the player you meant: "))
            if 1 <= choice <= len(matches):
                return matches[choice-1][0]
        except ValueError:
            pass
        return None
    
    # If still no match, try partial match
    matches = []
    for node, attrs in G.nodes(data=True):
        name = attrs.get('name', '')
        if isinstance(name, str) and player_lower in name.lower():
            matches.append((node, name))
    
    if len(matches) > 0:
        if len(matches) > 10:
            matches = matches[:10]  # Limit to 10 matches
        
        print(f"No exact match found. Did you mean one of these players?")
        for i, (player_id, name) in enumerate(matches, 1):
            print(f"{i}. {name}")
        try:
            choice = int(input("Enter the number of the player you meant (0 to search again): "))
            if 1 <= choice <= len(matches):
                return matches[choice-1][0]
        except ValueError:
            pass
    
    return None

def find_shortest_path(G, player1, player2):
    """Find the shortest path between two players"""
    # Try to get player IDs from player names
    id1 = get_player_id(G, player1)
    if not id1:
        return f"Player not found: {player1}", None, []
    
    id2 = get_player_id(G, player2)
    if not id2:
        return f"Player not found: {player2}", None, []
    
    # Convert IDs back to names for display
    p1_name = G.nodes[id1].get('name', id1)
    p2_name = G.nodes[id2].get('name', id2)
    
    try:
        # First find the shortest path length
        path_length = nx.shortest_path_length(G, source=id1, target=id2)
        
        # Then find a single shortest path
        path = nx.shortest_path(G, source=id1, target=id2)
        path_details = get_path_details(G, path)
        
        # Find all simple paths with the same length (limit to 10 to avoid excessive computation)
        all_paths = []
        
        # Use a generator to find paths without computing all at once (more memory efficient)
        for p in nx.all_simple_paths(G, source=id1, target=id2, cutoff=path_length):
            if len(p) == len(path):  # Only collect paths of the same length as the shortest
                all_paths.append(p)
                if len(all_paths) >= 10:  # Limit to 10 paths
                    break
        
        return path, path_details, all_paths
    
    except nx.NetworkXNoPath:
        return f"No connection found between {p1_name} and {p2_name}", None, []
    except nx.NodeNotFound:
        missing = []
        if id1 not in G:
            missing.append(p1_name)
        if id2 not in G:
            missing.append(p2_name)
        return f"Player(s) not found in graph: {', '.join(missing)}", None, []

def display_path(G, path, index=None):
    """Display a path with connection details"""
    if not path:
        return
    
    path_details = get_path_details(G, path)
    
    # Add path number if provided
    path_str = ""
    if index is not None:
        path_str = f"Path #{index+1}: "
    
    # Get player names from node attributes for first and last player
    first_player = G.nodes[path[0]].get('name', path[0])
    last_player = G.nodes[path[-1]].get('name', path[-1])
    
    print(f"\n{path_str}{first_player} to {last_player} ({len(path)-1} links):")
    
    for i in range(len(path_details)):
        p1, p2, connections = path_details[i]
        print(f"{p1} → {p2}")
        if connections:
            print("  Played together at:")
            for season, team in connections:
                print(f"  • {team} ({season})")
        else:
            print("  No team/season data available for this connection")

def get_all_players(G):
    """Return a list of all players in the graph with names and IDs"""
    players = []
    for node, attrs in G.nodes(data=True):
        name = attrs.get('name', node)
        players.append((name, node))
    
    # Sort by name
    return sorted(players, key=lambda x: x[0].lower())

def save_graph(G, filename="player_graph.gml"):
    """Save the graph to a file"""
    print("Saving graph to file (this may take a while)...")
    nx.write_gml(G, filename)
    print(f"Graph saved to {filename}")

def load_graph(filename="player_graph.gml"):
    """Load a graph from a file"""
    if Path(filename).exists():
        print(f"Loading graph from {filename}")
        return nx.read_gml(filename)
    else:
        print(f"Graph file {filename} not found.")
        return None

def main():
    parser = argparse.ArgumentParser(description='Football Player Connection Finder')
    parser.add_argument('--sample', type=int, help='Use a smaller sample size for testing')
    parser.add_argument('--rebuild', action='store_true', help='Force rebuilding the graph even if it exists')
    parser.add_argument('--csv', type=str, default='squads_cleaned.csv', help='CSV file to use')
    args = parser.parse_args()
    
    # Check if the graph file exists, otherwise build it
    graph_file = "player_graph.gml"
    
    if Path(graph_file).exists() and not args.rebuild:
        print(f"Loading existing graph from {graph_file}")
        G = load_graph(graph_file)
    else:
        print("Building new graph...")
        G = build_graph(args.csv, args.sample)
        save_graph(G, graph_file)
    
    if not G:
        print("Failed to load or build graph. Exiting.")
        return
    
    # Interactive loop
    while True:
        print("\n--- Player Connection Finder ---")
        print("1. Find connection between two players")
        print("2. List all players")
        print("3. Exit")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            player1 = input("Enter first player name: ")
            player2 = input("Enter second player name: ")
            
            path_result, path_details, all_paths = find_shortest_path(G, player1, player2)
            
            if isinstance(path_result, list):
                # Display first path
                display_path(G, path_result)
                
                # Show if there are alternative paths
                if len(all_paths) > 1:
                    print(f"\nFound {len(all_paths)} different paths with {len(path_result)-1} links.")
                    view_others = input("Would you like to see alternative paths? (y/n): ").lower()
                    
                    if view_others.startswith('y'):
                        # Skip the first path as we've already shown it
                        for i, alt_path in enumerate(all_paths[1:], 1):
                            display_path(G, alt_path, i)
                            
                            # If there are more paths, ask if user wants to continue
                            if i < len(all_paths) - 1:
                                continue_viewing = input("\nView next path? (y/n): ").lower()
                                if not continue_viewing.startswith('y'):
                                    break
            else:
                print(path_result)  # This is the error message
                
        elif choice == '2':
            players = get_all_players(G)
            print(f"\nTotal players: {len(players)}")
            search = input("Search for player (or press Enter to list all): ")
            
            if search:
                search_lower = search.lower()
                matching = [p for p in players if search_lower in p[0].lower()]
                print(f"Found {len(matching)} matching players:")
                for i, (name, player_id) in enumerate(matching[:20], 1):
                    print(f"{i}. {name}")
                if len(matching) > 20:
                    print(f"...and {len(matching) - 20} more")
            else:
                for i, (name, _) in enumerate(players[:20], 1):
                    print(f"{i}. {name}")
                print(f"...and {len(players) - 20} more")
                
        elif choice == '3':
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 