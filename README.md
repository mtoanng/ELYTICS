# Introduction 
PEMELY SHERLOCK application to view ELY asTested data.

# Databricks Connection Setup

To connect to Databricks DEV, create a file named `tokens.env` in the project root with the following content:

```
DATABRICKS_SERVER_HOSTNAME=adb-1032635496032522.2.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/9990e8fa0759e833
DATABRICKS_TOKEN=<your access token>
```

- **DATABRICKS_SERVER_HOSTNAME**: The hostname of your Databricks workspace.
- **DATABRICKS_HTTP_PATH**: The HTTP path for your Databricks SQL endpoint.
- **DATABRICKS_TOKEN**: Your Databricks personal access token (keep this secret, do not share or commit it).

> **Important:** Never commit your `tokens.env` file to version control. Only share a template or example file with your team.

# Getting Started
TODO: Guide users through getting your code up and running on their own system. In this section you can talk about:
1.   Installation process
2.   Software dependencies
3.   Latest releases
4.   API references


# Version History
See the [Version History](CHANGELOG.md) for release notes and changelog.

# Build and Test
TODO: Describe and show how to build your code and run the tests. 

# Contribute
TODO: Explain how other users and developers can contribute to make your code better. 

If you want to learn more about creating good readme files then refer the following [guidelines](https://docs.microsoft.com/en-us/azure/devops/repos/git/create-a-readme?view=azure-devops). You can also seek inspiration from the below readme files:
- [ASP.NET Core](https://github.com/aspnet/Home)
- [Visual Studio Code](https://github.com/Microsoft/vscode)
- [Chakra Core](https://github.com/Microsoft/ChakraCore)