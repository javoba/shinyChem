# Base R Shiny image
FROM rocker/shiny

# Make a directory in the container
RUN mkdir /home/shiny-app

# Install R dependencies
RUN R -e "install.packages(c('dplyr', 'ggplot2', 'pracma', 'plotly', 'readxl', 'shiny', 'shinyjs', 'nls2', 'htmlwidgets', 'bslib', 'shinythemes'))"

# Copy the Shiny app code
COPY Mass_Pross.R /home/shiny-app/app.R

# Expose the application port
EXPOSE 8180

# Run the R Shiny app
CMD ["R", "-e", "shiny::runApp('/home/shiny-app/app.R', host='0.0.0.0', port=8180)"]
