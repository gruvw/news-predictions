# Predictive Statements in the Press

## Categories

1. Boolean statements
   Examples:
      - "Mr. Jonh Doe will win the 2015 elections."
      - "It is going to rain Friday 19th 1985 in Lausanne."
      - "The Berlin Wall will fall in November 1989."
      - "It will snow in Geneva on Christmas Day next year."
      - "The stock market will close higher today than it did yesterday."
      - "The ceasefire will hold."
2. Numerical statements
   Examples:
      - "LHC club will score 5 goals against VISP tomorrow."
      - "Global oil prices will increase by $15 per barrel by the end of the quarter."
      - "Inflation will rise by 2% next year."
3. Duration
   Examples:
      - "The war will be over in two weeks."
      - "The bridge repair project will last for six months."
4. Dates
   Examples:
      - "The final software patch will be released on November 15, 2026."
      - "The patent will be accepted on December 12, 2032."
5. Ordinal statements (rankings)
   Examples:
      - "Norway will remain the happiest country in the world next year."
      - "Team X will finish in the top three of the league."
6. Ranges
   Examples:
      - "Temperatures will be between 28 and 32°C this weekend."
      - "The new tram line will cost between 200 and 250 million francs."
7. Probabilistic statements (or explicit confidence)
   Examples:
      - "There is a 70% chance of snow tomorrow."
      - "Analysts give the merger an 80% chance of approval."

## Topics

- Political (elections, referendums, government changes, treaties, legislation, regulations, ...)
- Economical (macroeconomics, prices, wages, exchange rates, unemployement, mortgage rate, home prices, rents, ...)
- Environmental (forecasts, floods, earthquakes, volcanic eruptions, heatwaves, snow, harvest conditions, ...)
- Sience/Technology (discoveries, research outcomes, adoption of inventions, performances, space exploration, ...)
- Infrastructure (project completion dates, delays, strikes, airline/rail disruptions, travel surges, ...)
- Health (population, epidemics, mortality, clinical trial results, ...)
- Sport/Events (race results, exhibitions, attendance, ...)
- Justice (trial verdicts, sentencing, court rulings, extradition, ...)
- Security (war outcomes, ceasefires, sanctions, crime rates, arrests, coups, terrorism risk, military deployments, data breaches, outages, ...)
- Energy (electricity prices, nuclear plant closures, renewable capacity, fuel shortages, ...)
- Education (exam results, university rankings, programs, ...)
- Business (corporate, Black Friday sales, holiday spending, earnings, mergers and acquisitions, IPOs, ...)
- Entertainment/Leisure (box office, award winners, album sales, streaming subscribers, vacations, travels, ...)
- Celebrity (marriages, divorces, retirements, comebacks, royal events, ...)
- Others

## Dataset Structure

- Impresso article ID or way to find the source of the statement
- Original statement (in original language and unalterted), start-end char
- Date of the statement
- (Original Author(s) of the statement, hard to do)
- Source of the statement (newspaper, report from other media)
- Resulting statement after pre-processing:
    - Translated to English
    - Converted relative times (next year > 2021, yesterday >February 18th)
    - Convert context ("The war" > "The wark against Ukraine")
- Time horizon of prediction (2 days, 1 year, etc) in days (0.3 days for hours)
- Category of prediction
- Predicted outcome (format determined by the category)

- Break multi-statements into different ones (ranking lists into ordinal, combinational statements)
- Topics of the statement (can be multiple, but as little as possible)

- Actual result (format determined by the category), with confidence?
- Source of actual result (link)
- Accuracy of the prediction (metric detemined by the category)
