"""Create VPC Link V2 and HTTP API after the internal ALB exists."""
import os
import boto3


def required(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit("Missing required environment variable: " + name)
    return value


region = required("AWS_REGION")
subnets = required("PRIVATE_SUBNET_IDS").split(",")
alb_name = required("ALB_NAME")
elbv2 = boto3.client("elbv2", region_name=region)
gateway = boto3.client("apigatewayv2", region_name=region)
alb = elbv2.describe_load_balancers(Names=[alb_name])["LoadBalancers"][0]
if alb["Scheme"] != "internal":
    raise SystemExit("ALB must be internal")
listener = elbv2.describe_listeners(LoadBalancerArn=alb["LoadBalancerArn"])["Listeners"][0]["ListenerArn"]
vpc_link_id = gateway.create_vpc_link(Name="pharma-vpc-link", SubnetIds=subnets)["VpcLinkId"]
api = gateway.create_api(Name="pharma-http-api", ProtocolType="HTTP")
integration = gateway.create_integration(ApiId=api["ApiId"], IntegrationType="HTTP_PROXY", IntegrationMethod="ANY", IntegrationUri=listener, ConnectionType="VPC_LINK", ConnectionId=vpc_link_id, PayloadFormatVersion="1.0")
gateway.create_route(ApiId=api["ApiId"], RouteKey="$default", Target="integrations/" + integration["IntegrationId"])
gateway.create_stage(ApiId=api["ApiId"], StageName="$default", AutoDeploy=True)
print(api["ApiEndpoint"])
