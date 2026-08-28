# Load libraries
library(readr)
library(dplyr)
library(tidyr)
library(xgboost)
library(caret)
library(pROC)
library(ggplot2)
library(reshape2)
library(dcurves)

# Load data
controls <- read_csv("control_results.csv")

cases <- read_csv("thal_res.csv")

# Add labels
cases$diagnosis <- 1
controls$diagnosis <- 0

# Combine
all_data <- bind_rows(cases, controls)

# Pivot to wide
wide_data <- all_data %>%
  select(subject_id, charttime, label, valuenum, diagnosis) %>%
  filter(!is.na(valuenum)) %>%
  group_by(subject_id, diagnosis, label) %>%
  arrange(desc(charttime)) %>%
  slice(1) %>%
  ungroup() %>%
  pivot_wider(
    id_cols = c(subject_id, diagnosis),
    names_from = label,
    values_from = valuenum
  )

# Features
feature_columns <- c("Hemoglobin","MCH","RDW","Red Blood Cells","MCV","Hematocrit","MCHC","Platelet Count","White Blood Cells")
existing_features <- feature_columns[feature_columns %in% names(wide_data)]

# Clean
wide_data_clean <- wide_data %>%
  select(subject_id, diagnosis, all_of(existing_features)) %>%
  drop_na()


# Train-test split
X <- as.matrix(wide_data_clean[, existing_features])
y <- wide_data_clean$diagnosis

set.seed(42)

train_idx <- unlist(
  lapply(
    split(seq_along(y), y),
    function(idx) sample(idx, size = floor(0.80 * length(idx)))
  )
)

train_idx <- sort(train_idx)

X_train <- X[train_idx, ]
y_train <- y[train_idx]

X_test <- X[-train_idx, ]
y_test <- y[-train_idx]


#Set base parameters
scale_pos_weight <- sum(y_train ==0)/ sum(y_train ==1)
cat("\nscale_pos_weight:", round(scale_pos_weight,2))

params <- list(
  objective ="binary:logistic",
  eval_metric ="auc",
  max_depth =6,
  eta =0.1,
  scale_pos_weight = scale_pos_weight
)


#Cross-Validation
feature_sets <- list(
  set1 = c("Hemoglobin","MCH","RDW","Red Blood Cells"),
  set2 = c("Hemoglobin","MCH","RDW","Red Blood Cells","MCV"),
  set3 = c("Hemoglobin","MCH","RDW","Red Blood Cells","MCV","Hematocrit"),
  set4 = c("Hemoglobin","MCH","RDW","Red Blood Cells","MCV","Hematocrit","MCHC"),
  set5 = c("Hemoglobin","MCH","RDW","Red Blood Cells","MCV","Hematocrit","MCHC","Platelet Count"),
  set6 = c("Hemoglobin","MCH","RDW","Red Blood Cells","MCV","Hematocrit","MCHC","Platelet Count","White Blood Cells")
)


folds <- createFolds(y_train, k = 5, list = TRUE, returnTrain = FALSE)

results <- data.frame()

for (set_name in names(feature_sets)) {
  features <- feature_sets[[set_name]]
  fold_aucs <- c()
  
  for (fold in 1:5) {
    # Get test indices for this fold
    test_idx <- folds[[fold]]
    train_idx <- setdiff(1:nrow(X_train), test_idx)
    
    # Split data
    X_fold_train <- X_train[train_idx, features]
    y_fold_train <- y_train[train_idx]
    X_fold_test <- X_train[test_idx, features]
    y_fold_test <- y_train[test_idx]
    
    # Calculate scale_pos_weight for this fold
    fold_scale_pos_weight <- sum(y_fold_train == 0) / sum(y_fold_train == 1)
    
    # Train model
    dtrain_fold <- xgb.DMatrix(data = X_fold_train, label = y_fold_train)
    dtest_fold <- xgb.DMatrix(data = X_fold_test, label = y_fold_test)
    
    params_fold <- list(
      objective = "binary:logistic",
      eval_metric = "auc",
      max_depth = 6,
      eta = 0.1,
      scale_pos_weight = fold_scale_pos_weight
    )
    
    model_fold <- xgb.train(
      params = params_fold,
      data = dtrain_fold,
      nrounds = 100,
      verbose = 0
    )
    
    # Evaluate
    pred_fold <- predict(model_fold, dtest_fold)
    auc_fold <- roc(y_fold_test, pred_fold)$auc
    fold_aucs <- c(fold_aucs, auc_fold)
  }
  
  results <- rbind(results, data.frame(
    feature_set = set_name,
    cv_auc = mean(fold_aucs, na.rm = TRUE)
  ))
}

print(results)
best_features <- feature_sets[[which.max(results$cv_auc)]]
cat("Best feature set:", paste(best_features, collapse = ", "), "\n")

# Test different max_depth values with cross-validation
depth_values <- c(4, 6, 8, 10)
depth_results <- data.frame()

for (depth in depth_values) {
  fold_aucs <- c()
  
  for (fold in 1:5) {
    # Get test indices for this fold
    test_idx <- folds[[fold]]
    train_idx <- setdiff(1:nrow(X_train), test_idx)
    
    # Use the best feature set from your previous test
    best_features <- feature_sets[[which.max(results$cv_auc)]]
    
    # Split data
    X_fold_train <- X_train[train_idx, best_features]
    y_fold_train <- y_train[train_idx]
    X_fold_test <- X_train[test_idx, best_features]
    y_fold_test <- y_train[test_idx]
    
    # Calculate scale_pos_weight for this fold
    fold_scale_pos_weight <- sum(y_fold_train == 0) / sum(y_fold_train == 1)
    
    # Train model with this depth
    dtrain_fold <- xgb.DMatrix(data = X_fold_train, label = y_fold_train)
    dtest_fold <- xgb.DMatrix(data = X_fold_test, label = y_fold_test)
    
    params_fold <- list(
      objective = "binary:logistic",
      eval_metric = "auc",
      max_depth = depth,
      eta = 0.1,
      scale_pos_weight = fold_scale_pos_weight
    )
    
    model_fold <- xgb.train(
      params = params_fold,
      data = dtrain_fold,
      nrounds = 100,
      verbose = 0
    )
    
    # Evaluate
    pred_fold <- predict(model_fold, dtest_fold)
    auc_fold <- roc(y_fold_test, pred_fold)$auc
    fold_aucs <- c(fold_aucs, auc_fold)
  }
  
  depth_results <- rbind(depth_results, data.frame(
    max_depth = depth,
    cv_auc = mean(fold_aucs, na.rm = TRUE)
  ))
}

print(depth_results)
best_depth <- depth_results$max_depth[which.max(depth_results$cv_auc)]
cat("Best Depth set:", best_depth, "\n")

# ---------------------------------------
# Determine optimal number of boosting rounds
# using 5-fold CV on the training data
# ---------------------------------------

X_train_final <- X_train[, best_features]

dtrain <- xgb.DMatrix(
  data = X_train_final,
  label = y_train
)

scale_pos_weight <- sum(y_train == 0) / sum(y_train == 1)

params_cv <- list(
  objective = "binary:logistic",
  eval_metric = "auc",
  max_depth = best_depth,
  eta = 0.1,
  scale_pos_weight = scale_pos_weight
)

set.seed(42)

cv_model <- xgb.cv(
  params = params_cv,
  data = dtrain,
  nrounds = 1000,
  nfold = 5,
  stratified = TRUE,
  early_stopping_rounds = 10,
  verbose = 1
)

# Find the iteration with the highest mean validation AUC
best_nrounds <- cv_model$evaluation_log$iter[
  which.max(cv_model$evaluation_log$test_auc_mean)
]

best_cv_auc <- max(cv_model$evaluation_log$test_auc_mean)

cat("Best number of rounds:", best_nrounds, "\n")
cat("Best mean CV AUC:", best_cv_auc, "\n")

# Check results
cat("Train cases:", sum(y_train == 1), "Controls:", sum(y_train == 0), "\n")
cat("Test cases:", sum(y_test == 1), "Controls:", sum(y_test == 0), "\n")

# ---------------------------------------
# Train final model on entire training set
# ---------------------------------------

X_train_final <- X_train[, best_features]
X_test_final <- X_test[, best_features]

dtrain <- xgb.DMatrix(
  data = X_train_final,
  label = y_train
)

dtest <- xgb.DMatrix(
  data = X_test_final,
  label = y_test
)

params_final <- list(
  objective = "binary:logistic",
  eval_metric = "auc",
  max_depth = best_depth,
  eta = 0.1,
  scale_pos_weight = scale_pos_weight
)

model <- xgb.train(
  params = params_final,
  data = dtrain,
  nrounds = best_nrounds,
  verbose = 1
)

# ---------------------------------------
# Final evaluation on untouched test set
# ---------------------------------------

predictions <- predict(model, dtest)

roc_obj <- pROC::roc(
  response = y_test,
  predictor = predictions
)

auc_val <- pROC::auc(roc_obj)

print(auc_val)

cat("Training cases:", sum(y_train == 1), "\n")
cat("Training controls:", sum(y_train == 0), "\n")
cat("Test cases:", sum(y_test == 1), "\n")
cat("Test controls:", sum(y_test == 0), "\n")

cat("Training case proportion:", mean(y_train), "\n")
cat("Test case proportion:", mean(y_test), "\n")

threshold <- coords(roc_obj,"best", ret ="threshold")$threshold
cat("\nOptimal threshold:", round(threshold,4))

#Confusion Matrix
pred_class <- ifelse(predictions > threshold, 1, 0)
cm <- table(Predicted = pred_class, Actual = y_test)
print(cm)

cm_df <- as.data.frame(cm)
names(cm_df) <- c("Predicted", "Actual", "Count")

# Plot confusion matrix
ggplot(cm_df, aes(x = Actual, y = Predicted, fill = Count)) +
  geom_tile(color = "white") +
  geom_text(aes(label = Count), size = 10, color = "black") +
  scale_fill_gradient(low = "white", high = "#008080") +  # Coral gradient
  labs(title = "Confusion Matrix", x = "Actual", y = "Predicted") +
  theme_minimal()

TN <- cm[1,1]; FP <- cm[2,1]; FN <- cm[1,2]; TP <- cm[2,2]
cat("Sensitivity:", round(TP / (TP + FN), 4), "\n")
cat("Specificity:", round(TN / (TN + FP), 4), "\n")

importance_matrix <- xgb.importance(model = model, feature_names = best_features)
print(importance_matrix)

# Feature Bar plot
# Calculate percentage of total gain
importance_matrix$Percent <- importance_matrix$Gain / sum(importance_matrix$Gain) * 100

ggplot(importance_matrix, aes(x = reorder(Feature, Gain), y = Gain)) +
  geom_bar(stat = "identity", fill = "#008080") +
  geom_text(aes(label = paste0(round(Percent, 1), "%")), hjust = -0.2, size = 4) +
  coord_flip() +
  labs(title = "Feature Importance",
       x = "Feature",
       y = "Gain") +
  theme_minimal() +
  ylim(0, max(importance_matrix$Gain) * 1.15)


# Plot ROC curve
roc_obj <- roc(y_test, predictions)
plot(roc_obj, 
     main = paste("ROC Curve - AUC =", round(auc_val, 4)),
     col = "#008080",
     lwd = 2)
abline(a = 0, b = 1, lty = 2, col = "gray")

# Calculate ROC coordinates
roc_obj <- roc(y_test, predictions)
roc_coords <- coords(roc_obj, "all", ret = c("threshold", "sensitivity", "specificity"))

# Plot sensitivity vs. specificity
ggplot(roc_coords, aes(x = 1 - specificity, y = sensitivity)) +
  geom_line(color = "#008080", linewidth = 1) +
  annotate("text", x = 0.5, y = 0.05, 
           label = paste("AUC =", round(auc_val, 4)), 
           size = 5, hjust = 0) +
  geom_abline(intercept = 0, slope = 1, linetype = "dashed", color = "gray") +
  labs(
    title = "ROC Curve",
    x = "1 - Specificity",
    y = "Sensitivity"
  ) +
  coord_equal() +
  theme_minimal()


#Confidence Interval
ci_auc <- ci(roc_obj)
print(ci_auc)

# Calculate accuracy
accuracy <- sum(diag(cm)) / sum(cm)
cat("Accuracy:", round(accuracy, 4), "\n")

# DCA curve
dtest <- xgb.DMatrix(data = X_test, label = y_test)
predictions <- predict(model, dtest)

dca_data <- data.frame(
  outcome = y_test,
  predictions = predictions
)

dca_result <- dca(
  formula = outcome ~ predictions,
  data = dca_data,
  thresholds = seq(0.1, 0.9, by = 0.05)
)

plot(dca_result, smooth = TRUE)

# Brier score (lower is better, 0.25 is random, 0 is perfect)
brier_score <- mean((predictions - y_test)^2)
cat("Brier Score:", round(brier_score, 4), "\n")

# Plot with confidence interval
plot(roc_obj, 
     main = paste("ROC Curve - AUC =", round(auc_val, 4)),
     col = "#008080",
     lwd = 3,
     grid = FALSE,
     legacy.axes = TRUE)

# Add confidence band
ci_roc <- ci(roc_obj, of = "se", specificities = seq(0, 1, by = 0.1))
plot(ci_roc, col = "#00808040", add = TRUE)

#All results in a table
library(htmlTable)

# Create a data frame with your metrics
metrics_df <- data.frame(
  Metric = c("AUC", "95% CI Lower", "95% CI Upper", "Sensitivity", "Specificity", "Accuracy", "Optimal Threshold"),
  Value = c(
    round(auc_val, 4),
    round(ci_auc[1], 4),
    round(ci_auc[3], 4),
    round(TP / (TP + FN), 4),
    round(TN / (TN + FP), 4),
    round(accuracy, 4),
    round(threshold, 4)
  )
)

# Display as HTML table in viewer pane
htmlTable(metrics_df, 
          caption = "Model Performance Metrics",
          align = "l")
ggplot(wide_data_clean, aes(x = as.factor(diagnosis), y = Hemoglobin, fill = as.factor(diagnosis))) +
  geom_boxplot() +
  labs(
    title = "RDW Distribution: Cases(BTT) vs Controls",
    x = "Diagnosis (0 = Control, 1 = Case)",
    y = "Hb (g/dL)",
    fill = "Diagnosis"
  ) +
  theme_minimal()

ggplot(wide_data_clean, aes(x = as.factor(diagnosis), y = Hemoglobin, fill = as.factor(diagnosis))) +
  geom_violin(alpha = 0.7) +
  geom_boxplot(width = 0.2, fill = "white") +
  labs(
    title = "RDW Distribution: Cases(BTM) vs Controls",
    x = "Diagnosis (0 = Control, 1 = Case)",
    y = "Hb (g/dL)"
  ) +
  theme_minimal() +
  theme(legend.position = "none")

xgb.save(model, "thal-model.xgb")
xgb.save(model, "thal-model.json")

training_features_thal <- as.data.frame(X_train_final)
write.csv(training_features_thal, "training_features_thal.csv", row.names = FALSE)
