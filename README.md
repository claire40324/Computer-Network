# Computer-Network

# Organization
The codebase is organized into several sub-directories as follows:

- `build_features/`: after collect the data, clean data and sort the features we want (Section 3.2)
- `collect_data/`: Data and scripts for the case studies (Section 3.1)
- `collect_data_test/`: collect the data for new RTT and BW that we can test our model
- `plot/` plot the picture that shows each congestion control in the top three importance of features (Section 4)
- `result/` confusion matrix and tables for test and validation (Section 4)
- `train_model/` Source code for training model (Section 3.3)
Each sub-directory has its own README.md file with further instructions.

We recommend exploring the codebase in the following order:

- collect the data (in collect_data/)
- build the features (in build_featuers/)
- train random forest model (in train_model/)
- see confusion matrix and table result  (in result/)
- try new RTT and Bandwidth for testing the model (in collect_data_test)
