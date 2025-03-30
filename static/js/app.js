$(document).ready(function() {
    // Set up player name autocomplete
    $(".player-autocomplete").autocomplete({
        source: function(request, response) {
            $.ajax({
                url: "/api/players",
                dataType: "json",
                data: {
                    q: request.term
                },
                success: function(data) {
                    response(data);
                }
            });
        },
        minLength: 2,
        select: function(event, ui) {
            $(this).val(ui.item.value);
            return false;
        }
    });

    // Clear button functionality
    $(".clear-btn").on("click", function() {
        const targetId = $(this).data("target");
        $("#" + targetId).val("");
    });

    // Form submission
    $("#search-form").on("submit", function(e) {
        e.preventDefault();
        
        const player1 = $("#player1").val().trim();
        const player2 = $("#player2").val().trim();
        
        if (!player1 || !player2) {
            showError("Please enter both player names");
            return;
        }
        
        // Show loading indicator
        $("#loading").removeClass("d-none");
        $("#results").addClass("d-none");
        $("#error-message").addClass("d-none");
        
        // Send the request to find connections
        $.ajax({
            url: "/api/find_connection",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({ player1, player2 }),
            dataType: "json",
            success: function(data) {
                $("#loading").addClass("d-none");
                
                if (data.success) {
                    displayResults(data.paths, player1, player2);
                } else {
                    showError(data.error);
                }
            },
            error: function(xhr) {
                $("#loading").addClass("d-none");
                showError("Error connecting to server. Please try again.");
            }
        });
    });

    // Function to display the results
    function displayResults(paths, player1, player2) {
        if (!paths || paths.length === 0) {
            showError("No connection found between these players");
            return;
        }
        
        // Create path selector buttons
        const pathSelector = $("#path-selector");
        pathSelector.empty();
        
        if (paths.length > 1) {
            pathSelector.append(`<span class="me-2">Paths:</span>`);
            paths.forEach((path, index) => {
                const activeClass = index === 0 ? "active" : "";
                pathSelector.append(`
                    <button type="button" class="btn btn-outline-primary btn-sm path-button ${activeClass}" 
                            data-path-index="${index}">
                        Path ${index + 1}
                    </button>
                `);
            });
        }
        
        // Update summary
        const firstPath = paths[0];
        $("#connection-summary").html(`
            <h5>${player1} and ${player2} are connected through ${firstPath.length} link${firstPath.length > 1 ? 's' : ''}.</h5>
            ${paths.length > 1 ? `<p class="text-muted">Found ${paths.length} different paths with the same number of links.</p>` : ''}
        `);
        
        // Display the first path
        displayPath(paths[0]);
        
        // Add click handlers for path buttons
        $(".path-button").on("click", function() {
            const pathIndex = $(this).data("path-index");
            $(".path-button").removeClass("active");
            $(this).addClass("active");
            displayPath(paths[pathIndex]);
        });
        
        // Show results
        $("#results").removeClass("d-none");
    }

    // Function to display a single path
    function displayPath(path) {
        const pathDisplay = $("#path-display");
        pathDisplay.empty();
        
        const playerNodes = path.nodes;
        const connections = path.connections;
        
        const pathHtml = $('<div class="player-path"></div>');
        
        // Add first player
        pathHtml.append(`
            <div class="path-step">
                <div class="player-card">
                    <h5>${playerNodes[0].name}</h5>
                </div>
            </div>
        `);
        
        // For each connection, display the connection info followed by the next player
        for (let i = 0; i < connections.length; i++) {
            const connection = connections[i];
            const nextPlayer = playerNodes[i + 1];
            const isLastStep = i === connections.length - 1;
            const stepClass = isLastStep ? "path-step last-step" : "path-step";
            
            // Build connection info
            const connectionHtml = $(`<div class="${stepClass}"></div>`);
            const connectionInfoBox = $('<div class="connection-info"></div>');
            
            if (connection.details && connection.details.length > 0) {
                // Sort connections by season (most recent first)
                const sortedDetails = [...connection.details].sort((a, b) => {
                    // Parse seasons like "2022-2023" and compare
                    const seasonA = a.season.split('-')[0];
                    const seasonB = b.season.split('-')[0];
                    return parseInt(seasonB) - parseInt(seasonA);
                });
                
                connectionInfoBox.append(`<h6>Played together at:</h6>`);
                const teamList = $('<div class="connection-details"></div>');
                
                sortedDetails.forEach(detail => {
                    teamList.append(`
                        <div class="connection-detail">
                            <span class="team-season">${detail.team}</span> 
                            <span class="season-year">(${detail.season})</span>
                        </div>
                    `);
                });
                
                connectionInfoBox.append(teamList);
                
                // Add number of shared teams for clarity
                if (sortedDetails.length > 1) {
                    // Group by team name to count distinct teams
                    const teams = new Set(sortedDetails.map(d => d.team));
                    if (teams.size > 1) {
                        connectionInfoBox.append(`<div class="mt-2 text-muted">
                            <small>Played at ${teams.size} different teams across ${sortedDetails.length} seasons</small>
                        </div>`);
                    } else {
                        connectionInfoBox.append(`<div class="mt-2 text-muted">
                            <small>Played together for ${sortedDetails.length} seasons</small>
                        </div>`);
                    }
                }
            } else {
                connectionInfoBox.append('<p>No team/season details available</p>');
            }
            
            connectionHtml.append(connectionInfoBox);
            pathHtml.append(connectionHtml);
            
            // Add next player
            pathHtml.append(`
                <div class="path-step">
                    <div class="player-card">
                        <h5>${nextPlayer.name}</h5>
                    </div>
                </div>
            `);
        }
        
        pathDisplay.append(pathHtml);
    }

    // Function to show error messages
    function showError(message) {
        let errorHtml = "";
        
        if (message.includes("No connection found between")) {
            // Customize the no connection error with suggestions
            const playerNames = message.replace("No connection found between ", "").split(" and ");
            if (playerNames.length === 2) {
                errorHtml = `
                    <div>
                        <h5 class="mb-3"><i class="bi bi-exclamation-triangle me-2"></i>No connection found between ${playerNames[0]} and ${playerNames[1]}</h5>
                        <p>This could be due to several reasons:</p>
                        <ul>
                            <li>These players may have never shared a team (directly or through other players)</li>
                            <li>One or both players might be in the database with a different spelling or name format</li>
                            <li>Try using full names (e.g., "Karim Benzema" instead of just "Benzema")</li>
                            <li>The connection might involve more players than our system can currently trace</li>
                        </ul>
                        <p>Try searching for other players these individuals might have played with first.</p>
                    </div>
                `;
            } else {
                errorHtml = `<h5>${message}</h5>`;
            }
        } else if (message.includes("Player not found")) {
            // Player not found error with suggestions
            const playerName = message.replace("Player not found: ", "");
            errorHtml = `
                <div>
                    <h5 class="mb-3"><i class="bi bi-person-x me-2"></i>Player not found: ${playerName}</h5>
                    <p>Suggestions:</p>
                    <ul>
                        <li>Check the spelling of the player's name</li>
                        <li>Try using the player's full name</li>
                        <li>The player might be known by a different name in our database</li>
                    </ul>
                </div>
            `;
        } else {
            // Default error message
            errorHtml = `<h5>${message}</h5>`;
        }
        
        $("#error-message").removeClass("d-none").html(errorHtml);
        $("#results").addClass("d-none");
    }
}); 