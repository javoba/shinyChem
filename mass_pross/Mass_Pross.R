rm(list = ls())
library(pracma)
library(ggplot2)
library(dplyr)
library(plotly)
library(readxl)
library(shiny)
library(shinyjs)
library(nls2) 
library(htmlwidgets)
library(bslib)
library(shinythemes)



options(shiny.maxRequestSize = 100*1024^2) # Increase file upload size limit to 100 MB

# UI
ui <- fluidPage(
  page_navbar(
    nav_item(
      input_dark_mode(id = "dark_mode", mode = "dark"), 
      div(
        style="display:inline-block;vertical-align:top;",
        actionButton("home", "home", onclick="location.href='https://shinychem.duckdns.org';")
      )
    )
  ),
  titlePanel("Processing of Mass Spectrometer data"),
  tabsetPanel(
    tabPanel("Plotting Options",
             sidebarLayout(
               sidebarPanel(
                 fileInput("plotFiles", "Choose CSV Files for Plotting",
                            multiple = TRUE,
                            accept = c("text/csv", ".csv")),
                 checkboxInput("normalizeData", "Normalize Data", value = FALSE),
                 #radioButtons("plotMode", "Plot Mode", choices = c("Separate Plots" = "separate", "Combined Plot" = "combined"))
                 
               ),
               mainPanel(
                 #plotlyOutput("plot1"),  # Include the plot directly here
                 #plotlyOutput("plot2"),
                 #plotlyOutput("plot3"),
                 plotlyOutput("combinedPlot")
                 
               )
             )
    ),
    tabPanel("Data Upload and process",
             sidebarLayout(
               sidebarPanel(
                 fileInput("file1", "Choose TXT File",
                           accept = c("text/txt", "text/comma-separated-values,text/plain", ".txt")),
                 actionButton("process", "Process Data")
               ),
               mainPanel(
                 textOutput("completionMessage"),
                 downloadButton("downloadData", "Download Processed Data")
               )
             )
    ),
    # New third tab for point selection
    tabPanel("Spectrum Processing",
             sidebarLayout(
               sidebarPanel(
                 fileInput("pointPlotDataFile", "Upload CSV File for Plotting",
                          accept = c("text/csv", ".csv")),
                 checkboxInput("normalizeData_points", "Normalize Data", value = FALSE),
                 radioButtons("radio", label = h4("Select processing type:"),
                              choices = list("Point labelling" = 1, "Difference calculations" = 2, "Cmax" = 3)), 
                 tableOutput("selectedPoints"),
                 tableOutput("selectedDifferencesmass"),
                 tableOutput("selectedDifferencessignal"),
                 
                 # Conditional panel for point labelling mode
                 conditionalPanel(
                   condition = "input.radio == 1",
                   h5("Selected Points:"),
                   tableOutput("selectedPoints")
                 ),
                 
                 # Conditional panel for Max # of C mode
                 conditionalPanel(
                   condition = "input.radio == 3",
                   h5("Max. # of C:"),
                   tableOutput("maxC")
                 ),
                 
                 # Conditional panel for difference calculations mode
                 conditionalPanel(
                   condition = "input.radio == 2",
                   h5("Differences in m/z:"),
                   tableOutput("selectedDifferencesmass"),
                   
                   h5("Differences in Intensity:"),
                   tableOutput("selectedDifferencessignal"),
                   
                   h5("Possible Fragments:"),
                   fileInput("fragments", "Choose an Excel Reference File",
                             accept = c(".xls", ".xlsx")),
                   tableOutput("fragmentMatches")
                 )
                 
               ),
               mainPanel(
                 plotlyOutput("plotpoints"),  # Include the plot directly here
               )
             )
    ),
    
    tabPanel("Spectral databanks",
             tags$br(), # line break
             tags$a("Spectral Database of Organic compounds", href = "https://sdbs.db.aist.go.jp/sdbs/cgi-bin/cre_index.cgi"),
             tags$br(), # line break
             tags$a("KnowItAllAnywhere", href = "https://www.knowitallanyware.com/search"),
             tags$br(), # line break
             tags$a("NIST", href = "https://webbook.nist.gov/chemistry/"),
             tags$br(), # line break
             tags$a("EnviPat", href = "https://www.envipat.eawag.ch/index.php"),
             
             
             
    )  
    
    
  )
  
  
)

# Server
server <- function(input, output, session) {
  
  # Reactive values
  data <- reactiveVal(NULL)
  fileProcessed <- reactiveVal(FALSE)
  
  # Function to process the file
  processFile <- function(filepath) {
    # Read the uploaded text file
    lines <- readLines(filepath)
    
    # Initialize vectors to store intensity and mass/position values
    intensity <- numeric()
    mass_position <- numeric()
    
    # Calculate total number of lines for progress bar
    total_lines <- length(lines)
    current_line <- 0
    
    # Loop through each line of the file
    for (line in lines) {
      current_line <- current_line + 1
      
      # Check if the line contains intensity and mass/position information
      if (grepl("intensity =", line) && grepl("mass/position =", line)) {
        # Split the line by comma to separate intensity and mass/position
        parts <- strsplit(line, ",")[[1]]
        intensity_part <- parts[grep("intensity =", parts)]
        mass_position_part <- parts[grep("mass/position =", parts)]
        
        # Extract the intensity and mass/position values
        intensity_value <- as.numeric(sub(".*=\\s*", "", intensity_part))
        mass_position_value <- as.numeric(sub(".*=\\s*", "", mass_position_part))
        
        # Append the values to the vectors
        intensity <- c(intensity, intensity_value)
        mass_position <- c(mass_position, mass_position_value)
      }
      
      # Update progress bar
      incProgress(current_line / total_lines, detail = paste("Processing line", current_line, "of", total_lines))
    }
    
    # Create a data frame with the two vectors
    data_frame <- data.frame(mass_position = mass_position, intensity = intensity)
    
    # Store the processed data in the reactive value
    data(data_frame)
    fileProcessed(TRUE)
  }
  
  # Observe when the file is uploaded and the process button is clicked
  observeEvent(input$process, {
    req(input$file1) # Ensure a file is uploaded
    
    # Reset progress bar
    withProgress(message = 'Processing data...', value = 0, {
      # Process the file
      processFile(input$file1$datapath)
    })
  })
  
  # Function to reset fileProcessed when a new file is selected
  observeEvent(input$file1, {
    fileProcessed(FALSE)
  })
  
  # Show completion message with the filename
  output$completionMessage <- renderText({
    if (fileProcessed()) {
      paste(input$file1$name, "processing completed!")
    } else {
      ""
    }
  })
  
  # Function to download processed data
  output$downloadData <- downloadHandler(
    filename = function() {
      paste0(gsub("\\.txt$", "_processed.csv", input$file1$name))
    },
    content = function(file) {
      write.csv(data(), file, row.names = FALSE)
    }
  )
  
  #For plots#####################
  
  # Render the combined plot
  output$combinedPlot <- renderPlotly({
    req(input$plotFiles)
    plot_data_list <- lapply(input$plotFiles$datapath, read.csv)
    file_names <- tools::file_path_sans_ext(basename(input$plotFiles$name))
    print(plot_data_list)
  
    
    p <- plot_ly()
    
    
    for (i in seq_along(plot_data_list)) {
      plot_data <- plot_data_list[[i]]
      
      # Check if headers are missing and add them if necessary
      if (!identical(names(plot_data), c("mass_position", "intensity"))) {
        names(plot_data) <- c("mass_position", "intensity")
      }
      
      if (input$normalizeData) {
        plot_data$intensity <- (plot_data$intensity - min(plot_data$intensity)) / (max(plot_data$intensity) - min(plot_data$intensity))
      }
      
      p <- add_lines(p, data = plot_data, x = ~mass_position, y = ~intensity, name = file_names[i]) %>%
        layout(xaxis = list(title = "m/z"), 
               yaxis = list(title = "Intensity"))
    }
    
    p
  })
  
  
  #For points#####################

  
  # Reactive value to store clicked points for point labelling mode
  clickedPoints <- reactiveVal(data.frame(x = numeric(), y = numeric()))
  
  # Reactive value to store clicked points for difference calculations mode
  differencePoints <- reactiveVal(data.frame(x = numeric(), y = numeric()))
  
  # Reactive value to store differences between points
  pointDifferences <- reactiveVal(data.frame(Point1_x = numeric(), Point1_y = numeric(), Point2_x = numeric(), Point2_y = numeric(), Diff_x = numeric(), Diff_y = numeric()))

  # Reactive value to store points for Cmax calculation
  click_Cmax <- reactiveVal(data.frame(int_1 = numeric(), int_2 = numeric()))
  
  # Reactive value to store differences between points
  point_Cmax <- reactiveVal(data.frame(Point1_x = numeric(), Point1_y = numeric(), Point2_x = numeric(), Point2_y = numeric(), Diff_x = numeric(), Diff_y = numeric()))
  

  output$plotpoints <- renderPlotly({
    req(input$pointPlotDataFile)
    # Read the uploaded CSV file for plotting
    plot_data <- read.csv(input$pointPlotDataFile$datapath)
    
    # Check if headers are missing and add them if necessary
    if (!identical(names(plot_data), c("mass_position", "intensity"))) {
      names(plot_data) <- c("mass_position", "intensity")
    }
    
    # Normalize data if the checkbox is checked
    if (input$normalizeData_points) {
      plot_data$intensity <- (plot_data$intensity - min(plot_data$intensity)) / (max(plot_data$intensity) - min(plot_data$intensity))
    }
    
    # Create the Plotly plot
    p <- plot_ly(data = plot_data, x = ~mass_position, y = ~intensity, type = 'scatter', mode = 'lines') %>%
        layout(xaxis = list(title = "m/z"), 
               yaxis = list(title = "Intensity"))
    
    # Register the 'plotly_click' event
    event_register(p, 'plotly_click')
    
    p
  })
  
  # Observe when a point is clicked on the plot
  observeEvent(event_data("plotly_click"), {
    click_data <- event_data("plotly_click")
    clicked_point <- data.frame(x = click_data$x, y = click_data$y)
    
    if (input$radio == 1) { # Point labelling mode
      clickedPoints(rbind(clickedPoints(), clicked_point))
    } else if (input$radio == 2) { # Difference calculations mode
      # Add the new point to difference points and calculate the difference
      current_points <- differencePoints()
      if (nrow(current_points) < 1) {
        differencePoints(rbind(current_points, clicked_point))
      } else {
        # Store the new points and their differences
        point1 <- current_points[1,]
        point2 <- clicked_point
        diff <- data.frame(Point1_x = point1$x, Point1_y = point1$y, Point2_x = point2$x, Point2_y = point2$y, 
                           Diff_x = abs(point2$x - point1$x), Diff_y = abs(point2$y - point1$y)) # Calculate absolute differences
        pointDifferences(rbind(pointDifferences(), diff))
        # Reset difference points
        differencePoints(data.frame(x = numeric(), y = numeric()))
      }
    } else if (input$radio == 3) { # Max # of C mode
      # Add the new point to difference points and calculate the difference
      current_points <- click_Cmax()
      if (nrow(current_points) < 1) {
        click_Cmax(rbind(current_points, clicked_point))
      } else {
        # Store the new points and their differences
        point1 <- current_points[1,]
        #print(point1$y)
        point2 <- clicked_point
        #print(point2$y)
        C_max <- data.frame(Point1_y = point1$y, Point2_y = point2$y,
                            Cmax = (100 * point2$y) / (1.1 * point1$y))
        point_Cmax(rbind(point_Cmax(), C_max))
        #print(point_Cmax)
        # Reset difference points
        click_Cmax(data.frame(x = numeric(), y = numeric()))
        #print(point_Cmax)
      }
      
      
      
      ## Store the new points and their differences
      #point1 <-  current_points[1,]
      #point2 <- clicked_point
      #clicked_point <- data.frame(intensity = click_data$y)
      ## Update clicked points for Max # of C mode
      #point_Cmax(rbind(point_Cmax(), clicked_point))
      
      #print(point_Cmax)
      }
  })
  
  # Render selected points table for point labelling mode
  output$selectedPoints <- renderTable({
    if (input$radio == 1) {
      clickedPoints() %>%
        rename("m/z" = x, "Intensity" = y) %>%  # Rename the columns
        mutate(across(everything(), ~ sprintf("%.5f", .)))  # Format numbers to have 5 decimal places
    }
  })
  
  
  # Render selected points table for Max # of C mode
  output$maxC <- renderTable({
    if (input$radio == 3) {
      point_Cmax() %>%
        rename("Intensity 1" = Point1_y, "Intensity 2" = Point2_y, "Cmax" = Cmax) %>%
        mutate(across(everything(), ~ sprintf("%.5f", .)))  # Format numbers to have 5 decimal places
    }
  })
  
  ## Render selected points table for point labelling mode
  #output$selectedPoints <- renderTable({
  #  if (input$radio == 1) {
  #    clickedPoints() %>%
  #      rename("m/z" = x, "Intensity" = y) %>%  # Rename the columns
  #      mutate(across(everything(), ~ sprintf("%.5f", .)),  # Format numbers to have 5 decimal places
  #             `m/z` = as.numeric(`m/z`),  # Convert m/z column to numeric
  #             #`m/z_rounded` = round(`m/z`),  # Round the m/z values
  #             "# N" = ifelse(as.integer(round(`m/z`)) %% 2 == 0, "Even", "Odd"))  # Add Nitrogen rule column
  #  }
  #})
  
  # Render differences table for m/z
  output$selectedDifferencesmass <- renderTable({
    if (input$radio == 2) {
      pointDifferences() %>%
        select(Point1_x, Point2_x, Diff_x) %>%
        rename("m/z 1" = Point1_x, "m/z 2" = Point2_x, "Difference m/z" = Diff_x) %>%
        mutate(across(everything(), ~ sprintf("%.5f", .)))  # Format numbers to have 5 decimal places
    }
  })
  
  # Render differences table for Intensity
  output$selectedDifferencessignal <- renderTable({
    if (input$radio == 2) {
      pointDifferences() %>%
        select(Point1_y, Point2_y, Diff_y) %>%
        rename("Intensity 1" = Point1_y, "Intensity 2" = Point2_y, "Difference Intensity" = Diff_y) %>%
        mutate(across(everything(), ~ sprintf("%.5f", .)))  # Format numbers to have 5 decimal places
    }
  })
  
  # Function to find possible fragments
  find_possible_fragments <- function(diffs, db) {
    matches <- lapply(diffs, function(diff) {
      db %>%
        filter(abs(Mass - diff) < 0.1) %>%
        select(Mass, `Possible Fragments`) %>%
        mutate(Difference = diff)
    })
    do.call(rbind, matches)
  }
  
  
  # Render possible fragment matches
  output$fragmentMatches <- renderTable({
    if (input$radio == 2) {
      # Load the database of mass differences and fragments
      req(input$fragments)
      mass_diff_db <- read_excel(input$fragments$datapath)
      
      diffs <- pointDifferences()$Diff_x
      #print(diffs)
      matches <- find_possible_fragments(diffs, mass_diff_db)
      #print(matches)
      matches
    }
  })
  


}

bs_global_theme()
# Run the application
shinyApp(ui, server)



















