import datetime
import decimal

import boto3.session as bsession
from boto3.dynamodb.conditions import Key
from pyrsistent import thaw

from task_processing.interfaces.persistence import Persister


class DynamoDBPersister(Persister):
    def __init__(self, table_name, endpoint_url=None, session=None):
        self.table_name = table_name
        if not session:
            session = bsession.Session()
        self.ddb_client = session.client(
            service_name='dynamodb',
            endpoint_url=endpoint_url,
        )
        self.table = session.resource(
            endpoint_url=endpoint_url,
            service_name='dynamodb'
        ).Table(table_name)

    def read(self, task_id, comparison_operator='EQ'):
        res = self.table.query(
            KeyConditionExpression=Key('task_id').eq(task_id)
        )
        return [self._replace_decimals(item) for item in res['Items']]

    def write(self, event):
        return self.ddb_client.put_item(
            TableName=self.table_name,
            Item=self._event_to_item(event)
        )

    def _event_to_item(self, e):
        raw = thaw(e)
        if type(raw) is dict:
            resp = {}
            for k, v in raw.items():
                if type(v) is str:
                    resp[k] = {
                        'S': v
                    }
                elif type(v) is int:
                    resp[k] = {
                        'I': str(v)
                    }
                elif type(v) is dict:
                    resp[k] = {
                        'M': self._event_to_item(v)
                    }
                elif type(v) is list:
                    if len(v) > 0:
                        resp[k] = []
                        for i in v:
                            resp[k].append(self._event_to_item(i))
                elif type(v) is datetime.datetime:
                    resp[k] = {
                        'N': str(int(v.timestamp()))
                    }
                elif type(v) is bool:
                    resp[k] = {
                        'BOOL': v
                    }
            return resp
        elif type(raw) is str:
            return {
                'S': raw
            }
        elif type(raw) is int:
            return {
                'I': str(raw)
            }
        else:
            print("Missed converting key %s type %s" % (raw, type(raw)))

    def _replace_decimals(self, obj):
        if isinstance(obj, list):
            return [self._replace_decimals(x) for x in obj]
        elif isinstance(obj, dict):
            return {k: self._replace_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        else:
            return obj
