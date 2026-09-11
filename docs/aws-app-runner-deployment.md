# Deploying better-gh to AWS App Runner

This guide creates a new single-instance deployment using the repository's
existing Docker image and GitHub Actions workflow:

`push to main -> GitHub Actions -> ECR :latest -> App Runner -> HTTPS`

## Important runtime limitations

- App Runner has no persistent filesystem. The SQLite preferences database is
  erased when the instance is replaced or redeployed.
- Configure exactly one instance (`min=1`, `max=1`). Multiple instances would
  have independent SQLite files, snapshots, tokens, and pollers.
- App Runner does not guarantee an always-running background CPU while an
  instance is idle. Watched-PR notifications are therefore best-effort when no
  requests are reaching the service.
- For durable preferences or reliable background jobs, replace SQLite with an
  external database and move polling/notifications to a scheduled worker.

## 1. Gather the deployment values

This guide uses:

```sh
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ECR_REPOSITORY=gh-dashboard
export APP_RUNNER_SERVICE=gh-dashboard
export GITHUB_OWNER=your-github-organization
export GITHUB_REPOSITORY=gh-dashboard
```

You need:

- an AWS account with permission to create IAM roles, ECR repositories, and
  App Runner services;
- administrator access to the GitHub repository;
- permission to register a GitHub OAuth App;
- AWS CLI and Docker only if bootstrapping from the command line.

## Minimal AWS access

Do not give the person deploying this application full
`AdministratorAccess`. The smallest practical setup uses three identities:

1. A human **bootstrap deployer** creates the ECR repository, secrets, IAM
   roles, and App Runner service.
2. The `gh-dashboard-ci` GitHub OIDC role can only pull and push this
   repository's ECR images.
3. The App Runner roles can only pull the image and read this application's
   runtime secrets.

The bootstrap deployer needs the following actions. Replace `AWS_ACCOUNT_ID`
and `AWS_REGION` before creating the policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageApplicationEcrRepository",
      "Effect": "Allow",
      "Action": [
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:DescribeImages",
        "ecr:GetLifecyclePolicy",
        "ecr:PutLifecyclePolicy",
        "ecr:TagResource"
      ],
      "Resource": "arn:aws:ecr:AWS_REGION:AWS_ACCOUNT_ID:repository/gh-dashboard"
    },
    {
      "Sid": "ManageApplicationSecrets",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:TagResource"
      ],
      "Resource": "arn:aws:secretsmanager:AWS_REGION:AWS_ACCOUNT_ID:secret:gh-dashboard/*"
    },
    {
      "Sid": "CreateApplicationRoles",
      "Effect": "Allow",
      "Action": [
        "iam:AttachRolePolicy",
        "iam:CreateRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:TagRole",
        "iam:UpdateAssumeRolePolicy"
      ],
      "Resource": "arn:aws:iam::AWS_ACCOUNT_ID:role/gh-dashboard-*"
    },
    {
      "Sid": "PassApplicationRolesOnly",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::AWS_ACCOUNT_ID:role/gh-dashboard-*"
    },
    {
      "Sid": "CreateAppRunnerServiceLinkedRoleOnce",
      "Effect": "Allow",
      "Action": "iam:CreateServiceLinkedRole",
      "Resource": "arn:aws:iam::*:role/aws-service-role/apprunner.amazonaws.com/AWSServiceRoleForAppRunner",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": "apprunner.amazonaws.com"
        }
      }
    },
    {
      "Sid": "ManageGitHubOidcProvider",
      "Effect": "Allow",
      "Action": [
        "iam:CreateOpenIDConnectProvider",
        "iam:GetOpenIDConnectProvider",
        "iam:ListOpenIDConnectProviders"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ManageAppRunnerService",
      "Effect": "Allow",
      "Action": [
        "apprunner:AssociateCustomDomain",
        "apprunner:CreateAutoScalingConfiguration",
        "apprunner:CreateService",
        "apprunner:DescribeAutoScalingConfiguration",
        "apprunner:DescribeCustomDomains",
        "apprunner:DescribeService",
        "apprunner:ListAutoScalingConfigurations",
        "apprunner:ListOperations",
        "apprunner:ListServices",
        "apprunner:ListTagsForResource",
        "apprunner:StartDeployment",
        "apprunner:TagResource",
        "apprunner:UpdateService"
      ],
      "Resource": "*"
    }
  ]
}
```

Notes:

- `iam:CreateOpenIDConnectProvider` is only needed if the account does not
  already have GitHub's OIDC provider. Remove that statement afterward.
- `iam:CreateServiceLinkedRole` is only needed when App Runner's AWS-managed
  service-linked role does not already exist in the account.
- AWS requires `Resource: "*"` for several App Runner creation/listing and
  OIDC-provider actions. The IAM role, ECR, and secret permissions remain
  restricted by name.
- If another administrator creates the OIDC provider and the three
  `gh-dashboard-*` roles, remove all IAM creation actions from the deployer.
  Keep only `iam:PassRole` for those roles.
- Deleting the deployment is intentionally excluded. Add
  `apprunner:DeleteService`, `ecr:DeleteRepository`,
  `secretsmanager:DeleteSecret`, and `iam:DeleteRole` only for an operator who
  is also responsible for teardown.
- If DNS is hosted in Route 53, the DNS administrator can add App Runner's
  records instead. Otherwise grant the deployer
  `route53:ChangeResourceRecordSets` only on the relevant hosted-zone ARN,
  plus `route53:GetHostedZone` and `route53:ListResourceRecordSets`.
- Viewing logs is not needed to deploy. For troubleshooting, separately grant
  read-only access to this service's CloudWatch log groups.

After bootstrap, routine application releases require no human AWS access:
GitHub Actions assumes the narrowly scoped `gh-dashboard-ci` role and pushes
the new image to ECR, then App Runner deploys it automatically.

## 2. Register a GitHub OAuth App

In GitHub, open **Settings -> Developer settings -> OAuth Apps -> New OAuth
App**.

For the initial setup, use the default App Runner URL after it is created. If
the final hostname is already known, use it now:

- Homepage URL: `https://gh.example.com`
- Authorization callback URL: `https://gh.example.com/auth/callback`

Save the client ID and generate a client secret. The callback URL must exactly
match `GITHUB_OAUTH_REDIRECT_URL`.

Generate the cookie-signing secret locally:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Do not commit either secret.

## 3. Create the ECR repository

```sh
aws ecr create-repository \
  --region "$AWS_REGION" \
  --repository-name "$ECR_REPOSITORY" \
  --image-scanning-configuration scanOnPush=true
```

Add an ECR lifecycle rule so immutable commit images do not accumulate
forever. Keep `latest` and approximately the last 30 commit-tagged images.

## 4. Allow GitHub Actions to push images

### Create the GitHub OIDC provider

In **IAM -> Identity providers**, add:

- Provider type: OpenID Connect
- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Skip this step if that provider already exists in the AWS account.

### Create the CI role

Create an IAM role named `gh-dashboard-ci` with this trust policy, replacing
the account, owner, and repository placeholders:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:GITHUB_OWNER/GITHUB_REPOSITORY:ref:refs/heads/main"
      }
    }
  }]
}
```

Attach this permissions policy, replacing the account and region:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeImages",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart"
      ],
      "Resource": "arn:aws:ecr:AWS_REGION:AWS_ACCOUNT_ID:repository/gh-dashboard"
    }
  ]
}
```

Update `.github/workflows/deploy.yml` for the new account:

- set `AWS_ACCOUNT_ID`;
- set `AWS_REGION`;
- replace `role-to-assume` with the new `gh-dashboard-ci` ARN.

For a reusable workflow, store these as GitHub repository variables instead of
hard-coding them.

Run the `deploy` workflow manually once. Confirm that ECR now contains both:

- `latest`;
- a tag matching the Git commit SHA.

## 5. Allow App Runner to pull from ECR

Create an IAM role named `gh-dashboard-apprunner-ecr`:

- Trusted entity: AWS service
- Service principal: `build.apprunner.amazonaws.com`
- Managed policy: `AWSAppRunnerServicePolicyForECRAccess`

This is the App Runner **ECR access role**, not the runtime instance role.

## 6. Store runtime secrets

Create separate AWS Secrets Manager secrets for:

- `gh-dashboard/github-oauth-client-secret`
- `gh-dashboard/session-secret`
- `gh-dashboard/linear-api-key` (optional)
- `gh-dashboard/cursor-api-key` (optional)

Create an App Runner instance role trusted by
`tasks.apprunner.amazonaws.com`. Grant it `secretsmanager:GetSecretValue`
only for those secret ARNs. Select this role as the service's runtime
**instance role**.

The GitHub OAuth client ID is not secret and can be a normal environment
variable.

## 7. Create the App Runner service

In **AWS App Runner -> Create service**:

1. Source: **Container registry**
2. Provider: **Amazon ECR**
3. Image URI:
   `AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/gh-dashboard:latest`
4. ECR access role: `gh-dashboard-apprunner-ecr`
5. Automatic deployments: **Enabled**
6. Port: `8080`
7. Health check: **TCP**
8. Suggested initial size: `0.25 vCPU / 0.5 GB`
9. Auto-scaling configuration: **minimum 1, maximum 1**
10. Runtime instance role: the Secrets Manager role from the previous step

Configure these normal environment variables:

```text
GITHUB_OAUTH_CLIENT_ID=<oauth client id>
GITHUB_OAUTH_REDIRECT_URL=https://gh.example.com/auth/callback
COOKIE_SECURE=true
PREFS_DB_PATH=/tmp/better-gh.sqlite3
OAUTH_SCOPES=repo,read:org
POLL_INTERVAL_SECONDS=300
IDLE_TTL_SECONDS=900
MAX_PRS=50
DEV_LOGIN=false
```

Map these environment variables to Secrets Manager:

```text
GITHUB_OAUTH_CLIENT_SECRET
SESSION_SECRET
LINEAR_API_KEY       # optional
CURSOR_API_KEY       # optional
```

Optional non-secret settings are documented in `backend/.env.example`:

```text
REVIEWER_LOGIN
MERGE_METHOD
LINEAR_TICKET_PREFIX
LINEAR_WORKSPACE_URL
BOT_LOGINS
PREVIEW_COMMENT_PREFIX
```

After creation, App Runner provides an `awsapprunner.com` hostname. If using
that hostname initially, update both the OAuth App callback and
`GITHUB_OAUTH_REDIRECT_URL` to match it exactly.

## 8. Add the custom domain

In the App Runner service, choose **Custom domains -> Link domain** and enter
the desired hostname, such as `gh.example.com`.

Add the validation and routing records App Runner displays to the DNS zone.
Wait for certificate validation, then change:

- GitHub OAuth homepage URL to `https://gh.example.com`;
- GitHub OAuth callback URL to `https://gh.example.com/auth/callback`;
- App Runner's `GITHUB_OAUTH_REDIRECT_URL` to the same callback URL.

App Runner supplies and renews the TLS certificate.

## 9. Verify the deployment

```sh
curl -I https://gh.example.com/
curl -I https://gh.example.com/login
```

Expected behavior:

- `/` redirects an unauthenticated request to `/login`;
- `/login` returns the sign-in page;
- GitHub sign-in returns to `/auth/callback`;
- the dashboard loads PR data after sign-in;
- a push to `main` runs tests, publishes a new `latest` image, and triggers an
  App Runner deployment.

Check App Runner logs if OAuth fails. The most common causes are:

- callback URL mismatch;
- missing Secrets Manager permission on the instance role;
- `COOKIE_SECURE` not set to `true`;
- a rotated `SESSION_SECRET`;
- organization restrictions on the GitHub OAuth App.

## 10. Operational settings

- Set an AWS Budget alert before launch.
- Keep App Runner at one instance until state is externalized.
- Add an ECR lifecycle policy.
- Retain the immutable SHA image tags for rollback.
- To roll back, temporarily deploy a known SHA-tagged image instead of
  `latest`, verify it, and then restore the normal `latest` deployment flow.
- Treat local SQLite data as disposable on App Runner.

At current us-east-1 rates, a low-traffic single instance usually costs about
$5-$20/month depending on its size and active CPU time, plus small ECR, log,
DNS, and transfer charges.
