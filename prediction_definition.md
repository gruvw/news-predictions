# How do we define a prediction?

Defining a prediction depends on the level of certainty a statement carries: For instance, the prediction "There will be a meeting every Monday during next Winter".  Winter will always happen, but it's not clear if a meeting that's scheduled for next Monday will.  
At the basis, all predictive statements have a binary outcome. We need to break the predictions we find down to the atomic predictive statements that could carry the slightes uncertainty and determine their binary outcome with sources from the future relative to it.

### Example:
"England will win against Spain in this year's World Cup final match with a score of 3:2."
The statement is interpreted as what it is most likely to mean in it's given contex.
It could contain multiple atomic statements:
- "England will win against Spain in the 1954 World cup final match."
- "The score of that match will be 3:2."

**Context** is alway implied for each prediction, otherwise it could be picked apart and driven to absurdity.


We cannot determine disjunct categories for predictive statements. Therefore, we break each one down in it's atomic parts that can have a binary outcome.

### The Definition of a Prediction

- Theoretically, any statement can be a prediction -> show the Englang vs Spain example with atomic predictions highlighted in color
- To remain limited in scope, we defined a prediction to be what we think the author of the prediction quote expects the context to be (what he expects to remain/be true).

- The problem is not determining what a prediction  is, but figuring out which predictions we can feasibly confirm with appropriate sources.

### Confidence Expression   
 prediction like "Spain will win the world cup." carries a much higher confidence than "Spain has good chances to win this world cup."
- This is valuable information that should be extracted and recorded in the database
- Probable solution: Use specialized model to determine confidence based on used language.


## The Wording of Predictions
- Statements using **future tense** can be prediction if they carry some uncertainty.
- **Key words** like "expect" that can be in present tense


## Conditional Predictions
"If Party X wins the election, it will introduce new economic reforms."

This contains a conditional future claim, but its verification requires two steps:
1. Did Party X win?
2. If so, were the reforms introduced?
I would initially exclude these from your main accuracy analysis, but retain them in a separate category.

**Possible Approach** to include them in the dataset
- For each conditional statement, check if it is a prediction by evaluating if the condition is met
- Put the whole statement inlcluding the conditional outcome as a prediction in the dataset
