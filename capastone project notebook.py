# Databricks notebook source
filename = dbutils.widgets.get('filename')
file  = filename.split(".")[0]
print(filename)

# COMMAND ----------

mounted = True
for x in dbutils.fs.mounts():
    if x.mountPoint == "/mnt/sales":
        print("already mounted")
        mounted = True
        break
    else:
        mounted = False

if not mounted:
    dbutils.fs.mount(source = 'wasbs://sales@dlk1012.blob.core.windows.net',mount_point = '/mnt/sales',extra_configs={'fs.azure.account.key.dlk1012.blob.core.windows.net':dbutils.secrets.get('databricksScope', 'dlkaccesskey')})
    print("mounted successfully")
else:
    print("already mounted")

# COMMAND ----------

df = spark.read.csv("/mnt/sales/landing/{}".format(filename),header = True)

total_orders = df.count()
total_distinct_order = df.select("order_id").distinct().count()

errorFlag = True
if total_orders == total_distinct_order:
    errorFlag = False

if errorFlag:
    dbutils.fs.mv("/mnt/sales/landing/{}".format(filename),"/mnt/sales/discarded/")
    dbutils.notebook.exit('{"errorFlag":"true","errormsg":"order id repeated"}')

# COMMAND ----------

dbServer = 'capstoneserver1212'
dbPort = '1433'
dbName = 'capastonedb '
dbUser = 'pavan'
dbPassword = 'sql-password'


connectionUrl ='jdbc:sqlserver://{}.database.windows.net:{};database={};user={};'.format(dbServer,dbPort, dbName, dbUser)
dbPassword = dbutils.secrets.get('salesprojectscope','sqlpass')
connectionProperties = {'password': dbPassword, 'driver':'com.microsoft.sqlserver.jdbc.SQLServerDriver' }


# COMMAND ----------

df_order_status  = spark.read.jdbc(url = connectionUrl,table = 'dbo.valid_order_status',properties=connectionProperties)

# COMMAND ----------

from pyspark.sql.functions import *

df_status_list = [data[0] for data in df_order_status.select('status_name').distinct().collect()]
invalidrowsDf = df.filter(~col('order_status').isin(df_status_list))

# COMMAND ----------

errorFlag = True

if invalidrowsDf.count()>0:
    errorFlag = False
    dbutils.fs.mv("/mnt/sales/landing/{}".format(filename),"/mnt/sales/discarded")
    dbutils.notebook.exit('{"errorFlag":"true","errormsg":"invalid order_status"}')
else:
    dbutils.fs.mv("/mnt/sales/landing/{}".format(filename),"/mnt/sales/staging")

# COMMAND ----------

df_customers  = spark.read.jdbc(url = connectionUrl,table = 'dbo.customers',properties=connectionProperties)

# COMMAND ----------

df_orders = spark.read.csv("/mnt/sales/staging/{}".format(filename),header=True,inferSchema = True)
# df_orders = spark.read.csv("/mnt/sales/staging/orders_new.csv",header=True,inferSchema = True)

# COMMAND ----------

df_order_items = spark.read.csv("/mnt/sales/orders_items/order_items.csv",header=True,inferSchema = True)

# COMMAND ----------

joined_df = df_orders.join(df_customers,df_orders.customer_id == df_customers.customer_id).drop(df_orders.customer_id)

# COMMAND ----------

join3df = joined_df.join(df_order_items,joined_df.order_id == df_order_items.order_item_order_id).drop(df_order_items.order_item_order_id)

# COMMAND ----------

from pyspark.sql.functions import *
final_df = join3df.groupBy("customer_id")\
    .agg(sum(col("order_item_subtotal")).alias("total_amount"),
         count(col("order_id")).alias("orders_count"))

# COMMAND ----------

final_df.write\
    .jdbc(url = connectionUrl,table = 'dbo.salesreporting',properties=connectionProperties,mode = 'overwrite')


# COMMAND ----------

dbutils.notebook.exit('{"msg":"published sales reporting"}')

# COMMAND ----------


