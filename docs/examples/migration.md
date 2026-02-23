# Example page migration from a space to Holmes

Below is an example of migrating a page from one of the spaces (Sherlock, Mycroft etc) into this Holmes repository. It's almost as simple as copy and pasting, there are just a couple of things to keep in mind.

| ID | Sherlock (legacy logic) | Holmes |
|---|---|---|
| 0 | [Monolithic](https://en.wikipedia.org/wiki/Monolithic_application) web application | [Client-Server](https://en.wikipedia.org/wiki/Front_end_and_back_end) architecure  |
| 1 | Databricks service to query data | Holmes has it's own [backend](../backend.md), which handles all data retrieval |
| 2 | Loads data on app startup | [Lazy loads](https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/Lazy_loading) data on each page requested by user |

Both of these architectural changes have their reasons, backend supporting the lazy loading. Please read the hyperlinked text in the table learn more. In the steps below, we will show what these changes looks like in terms of the codebase.

## 1. What page do we want to migrate?

For this example we'll be using the order overview page from the Sherlock explore category. Please see the file [here](https://dev.azure.com/BoschTransmissionTechnology/ELY%20Analytics%20Solution/_git/TBP-SHERLOCK?path=/pages/explore/order.py), I won't be including a snippet of the entire file here as it's quite large. 

## 2. Lets start with monolithic migration (0)

We need to migrate the `./pages/explore/order.py` and any files it uses, in this case that's also `./services/databricks_service.py` and `./queries/order_overview.sql`. During this step, we need to identify what files need to be added or modified. 

|Sherlock | Holmes | Type | Justification |
|---|---|---|---|
|`./pages/explore/order.py` | `./frontend/spaces/sherlock/explore/order_overview.py` | New file | As this is for Sherlock, we choose the Sherlock space directory. File is also renamed to match the title of the page itself. |
|`./queries/order_overview.sql` | `./backend/queries/sherlock/order_overview.sql` | New file (copy query) | As this is for Sherlock, we choose the Sherlock space directory. |
|`./services/databricks_service.py` | `./backend/routers/sherlock/tables.py` | Modify | As this is for Sherlock, we need to modify the tables route for the Sherlock space to include this table. |

As for the modification of the `./backend/routers/sherlock/tables.py`, this is quite simply, you just need to add the code below:

```python
@router.get("/order_overview")
async def order_overview(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))): 
    return {"data": get_query_result(f"{SPACE}/order_overview")}
```

And that's it for the backend! Everything else is already setup to automatically ingest things, like polling Databricks, storing in Redis and fetching latest value. We'll cover the `order_overview.py` migration in the next step, as it's a little more hands on.

## 3. Using our backend (1)

In this step we'll cover using the backend, and adapting our pages logic to use lazy loading. First I recommend you take a look at [`./frontend/services/backend_service.py`](../../frontend/services/backend_service.py), here you can see how we setup our communication with the backend - it's quite simple, the important thing to note here, is that the request has proper authentication and formats the response to a pandas Dataframe so our page can use it without any additional changes.

The key function is `get_table_as_df(space, table_name)` which takes:
- `space`: the space name (e.g., "sherlock", "watson", "mycroft")  
- `table_name`: the name of the table/query (e.g., "order_overview")

And returns a pandas DataFrame that's ready to use.

### Key difference: Lazy Loading vs Startup Loading

**Old approach (Sherlock):**
```python
# Data loaded ONCE when the app starts
df = service.execute_query(query)
# ...
layout = html.Div([
    dag.AgGrid(rowData=df.to_dict("records"), ...)  # Static data
])
```

**New approach (Holmes):**
```python
# Data loaded WHEN the user visits the page
@callback(
    Output("order-data-store", "data"),
    Input("order-order-table", "id"),
)
def load_order_data(_):
    df = get_table_as_df('sherlock', "order_overview")
    # ... process data ...
    return df.to_dict("records")

layout = html.Div([
    dcc.Store(id="order-data-store"),  # Empty at startup
    dag.AgGrid(id="order-order-table", rowData=[], ...)  # Empty initially
])
```

This lazy loading is better for performance because:
1. **Faster startup** - The app loads quickly without waiting for all queries
2. **Fresh data** - Each user gets the latest data when they visit the page
3. **Scalability** - Multiple users can access the app without overloading the database

## 4. The Lazy Loading Pattern (2)

Now let's understand the mechanics. There are typically 2-3 callbacks on a lazy-loaded page:

### First Callback - Load Data on Page Init

This callback fires when the page loads and populates the data store:

```python
@callback(
    Output("order-data-store", "data"),           # Where to store the data
    Input("order-order-table", "id"),             # Triggers when table is rendered
)
def load_order_data(_):
    df = get_table_as_df('sherlock', "order_overview")
    
    # Any data processing (rounding, formatting, etc.)
    max_cols = [col for col in df.columns if col.endswith('_max')]
    if max_cols:
        df[max_cols] = df[max_cols].round(2)
    
    return df.to_dict("records")
```

**What's happening:**
- `Input("order-order-table", "id")` - This triggers when the AgGrid component first appears
- The function fetches data from the backend via `get_table_as_df()`
- Data is processed (rounding, cleaning, etc.)
- Data is stored in `dcc.Store` for use by other callbacks

### Second Callback - Update Table with Filters

This callback handles filtering logic and updates the table display:

```python
@callback(
    Output("order-order-table", "rowData"),              # Update the table
    Output("order-order-id-filter", "options"),          # Update filter options
    # ... other filter outputs ...
    Input("order-order-id-filter", "value"),             # When filters change
    Input("order-sample-name-filter", "value"),
    # ... other filter inputs ...
    Input("order-data-store", "data"),                   # When data loads
    prevent_initial_call=True,
)
def update_table(order_id, sample_name, ..., data):
    if not data:
        return [], [], [], [], []
    
    df = pd.DataFrame(data)
    dff = df.copy()
    
    # Apply filters
    if order_id:
        dff = dff[dff["order_id"].isin(order_id)]
    if sample_name:
        # ... filter logic ...
    
    # Return both the filtered rows AND updated filter options
    return records, order_id_options, sample_name_options, ...
```

**What's happening:**
- This callback is triggered whenever a filter changes OR when new data loads
- It reads data from the store, filters it based on user selections
- It returns both the filtered table data AND updated options for all dropdowns (so other filters only show valid values)

### Third Callback - Handle Double-Click Filtering

This is a convenient feature where double-clicking a cell filters by that value:

```python
@callback(
    Output("order-order-id-filter", "value"),      # Update this filter
    Output("order-sample-name-filter", "value"),   # Update this filter
    # ... other filter outputs ...
    Input("order-order-table", "cellDoubleClicked"),  # When a cell is double-clicked
    prevent_initial_call=True
)
def update_filter_on_cell_dblclick(cell):
    if not cell or "colId" not in cell:
        raise no_update
    
    col = cell["colId"]
    val = cell["value"]
    
    # Set the corresponding filter to the cell value
    if col == "order_id":
        return val, None, None, None
    elif col == "sample_name":
        return None, val, None, None
    # ... etc ...
```

**What's happening:**
- User double-clicks a cell (e.g., a specific Order ID)
- The callback captures which column and what value was clicked
- It sets the corresponding filter to that value
- The second callback then re-runs and updates the table with the filter applied

## 5. Common Migration Checklist

When migrating a page, follow these steps:

- [ ] **Backend Setup**
  - [ ] Copy the SQL query file to `./backend/queries/{space}/{table_name}.sql`
  - [ ] Add a route to `./backend/routers/{space}/tables.py`:
    ```python
    @router.get("/{table_name}")
    async def table_name(token=Depends(require_groups(["IdM2BCD_holmes_pemely_user"]))):
        return {"data": get_query_result(f"{SPACE}/{table_name}")}
    ```

- [ ] **Frontend Setup**
  - [ ] Create a new page file: `./frontend/spaces/{space}/{category/{page_name}.py`
  - [ ] Add `register_page()` with the correct path and title
  - [ ] Import `get_table_as_df` from `services.backend_service`
  - [ ] Create layout function (remove startup data loading)
  - [ ] Add `dcc.Store` for data storage
  - [ ] Move all data filtering logic to callbacks

- [ ] **Update Callbacks**
  - [ ] Created data loading callback (triggers on page load)
  - [ ] Update filtering callback (uses stored data)
  - [ ] Update download callback (if needed)

- [ ] **Testing**
  - [ ] Verify data loads when page is visited
  - [ ] Test each filter works correctly
  - [ ] Test filter combinations work together
  - [ ] Download CSV functionality works
  - [ ] No errors in browser console

## 6. Common Patterns

### Pattern: CSV Download

```python
@callback(
    Output("download-csv", "data"),
    Input("download-btn", "n_clicks"),
    State("table", "rowData"),
    prevent_initial_call=True,
)
def download(n_clicks, table_data):
    if not table_data:
        return no_update
    df = pd.DataFrame(table_data)
    return dcc.send_data_frame(df.to_csv, "export.csv", index=False)
```

### Pattern: Multi-Select Filtering

```python
if filter_value:
    if isinstance(filter_value, list):
        # User selected multiple values
        dff = dff[dff["column"].isin(filter_value)]
    else:
        # User selected single value (shouldn't happen with multi=True, but safe to handle)
        dff = dff[dff["column"] == filter_value]
```

### Pattern: Handling Null/None Values

When a column contains null values, Dash doesn't display them well. Convert them to the string "Null" for display:

```python
{"label": str(value) if value is not None else "Null", 
 "value": str(value) if value is not None else "Null"}
```

When filtering, remember to check for these "Null" strings and compare appropriately.

## 7. Asking for Help

This process can be automated! If you have a page you want to migrate:

1. **Prepare the SQL query** - Move it to `./backend/queries/{space}/{table_name}.sql`
2. **Add backend route** - Add the endpoint to the tables router
3. **Share the old page file** with an LLM (like GitHub Copilot) and ask it to convert it to the new format

Example prompt:
```
"Convert this Dash page to use lazy loading and callbacks. 
 Use get_table_as_df('sherlock', 'order_overview') instead of 
 loading data at startup. The old imports are... [paste old code]"
```

Most LLMs can handle this conversion automatically, which saves a lot of time.

