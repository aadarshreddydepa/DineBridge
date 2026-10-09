# AWS trial deployment (one EC2 instance)

This is a learning and demonstration deployment. It runs PostgreSQL, Django, and the React site on one EC2 instance with Docker Compose. Caddy serves HTTPS and routes `/api/*` and `/q/*` to Django, so guest and staff cookies stay on the same origin. PostgreSQL is reachable only inside the Docker network. It has one server and no automatic off-instance backups; do not use it for live restaurant service.

## 1. Before launching an instance

1. In AWS Billing, inspect your account's Free Tier/credit eligibility and create a small monthly cost budget with email alerts. AWS benefits differ by account creation date and account plan. A running instance, EBS disk, public IPv4, and data transfer can consume credits or incur charges.
2. Choose one AWS Region near you, such as Mumbai (`ap-south-1`) if appropriate. Keep all resources in that Region.
3. In EC2, launch **Ubuntu Server 24.04 LTS**, an x86_64 image, with a **t3.small** (2 GiB RAM) for this Compose stack. Verify the instance type is eligible for *your* account's Free Tier or credits before launching. Use a 20 GiB `gp3` root volume. Create/download an SSH key pair (`.pem`) and keep it private.
4. Create a security group with inbound TCP **22 from My IP only**, **80 from Anywhere**, and **443 from Anywhere**. Allow outbound traffic. Do not open 5432 or 8000.
5. Start with the instance's assigned public IPv4. The trial URL can use `<public-ip-with-dashes>.sslip.io`, for example `1-2-3-4.sslip.io`. This free DNS service maps the embedded IP to the instance. A normal domain with an A record to the public IP also works. The instance's assigned public IPv4 changes when it is stopped and started; a static Elastic IP is available but has a charge. If the IP changes, update the hostname configuration and reprint QRs.

Wait for EC2 status checks to pass. In the commands below, replace `YOUR_IP`, `YOUR_KEY.pem`, and `YOUR_HOSTNAME` with your actual values. Do not type the angle brackets.

## 2. Install Docker on Ubuntu

On your Mac, connect with:

```sh
chmod 400 ~/Downloads/YOUR_KEY.pem
ssh -i ~/Downloads/YOUR_KEY.pem ubuntu@YOUR_IP
```

On EC2, install Docker Engine and the Compose plugin using Docker's official Ubuntu repository:

```sh
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker compose version
```

The `sudo docker` commands below avoid adding your account to the Docker group, which grants root-equivalent access.

## 3. Get the code with Git

On your **Mac**, commit and push the AWS deployment files first. `git clone` can only download committed and pushed files. Review `git status` and ensure `.env`, `deploy/aws.env`, and `.local-demo-credentials.json` are not staged.

```sh
cd /path/to/DineBridge
git add .gitignore README.md compose.aws.yaml deploy/init-aws-env.sh deploy/aws.env.example docs/aws-trial.md frontend/.dockerignore frontend/Caddyfile.aws frontend/Dockerfile.aws
git diff --cached --check
git diff --cached --stat
git commit -m "Add AWS trial deployment setup"
git push origin main
```

On **EC2**, use one of these options:

- **Public GitHub repository:** `git clone https://github.com/aadarshreddydepa/DineBridge.git ~/dinebridge`
- **Private GitHub repository:** create a read-only GitHub deploy key on EC2, add its **public** half under the repository's **Settings → Deploy keys**, then clone with the SSH URL. Do not copy your personal GitHub password or token onto EC2.

```sh
ssh-keygen -t ed25519 -f ~/.ssh/dinebridge_deploy -C dinebridge-ec2 -N ''
cat ~/.ssh/dinebridge_deploy.pub
# Add the displayed public key to GitHub; leave “Allow write access” unchecked.
GIT_SSH_COMMAND='ssh -i ~/.ssh/dinebridge_deploy -o IdentitiesOnly=yes' \
  git clone git@github.com:aadarshreddydepa/DineBridge.git ~/dinebridge
```

Run the SSH clone command only for a private repository after adding the deploy key. Verify the GitHub host key when SSH first asks; compare it with GitHub's published fingerprint. The AWS secrets file is created on EC2 in the next step and is ignored by Git.

## 4. Configure and start the app

Reconnect to EC2 and run:

```sh
cd ~/dinebridge
bash deploy/init-aws-env.sh YOUR_HOSTNAME
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml config --quiet
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml build
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml up -d db api
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml run --rm api python db/migrate.py
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml up -d web
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml ps
```

Use a hostname without `https://` when running `init-aws-env.sh`. It creates unique database and Django secrets in `deploy/aws.env` with file mode 600. Keep this file private and back it up securely. Caddy obtains and renews a public HTTPS certificate; initial issuance can take a few minutes. Ports 80 and 443 must reach the instance, and the hostname must resolve to its public IP.

Check from your Mac:

```sh
curl -f https://YOUR_HOSTNAME/healthz
```

The site should open at `https://YOUR_HOSTNAME/` and the staff login at `https://YOUR_HOSTNAME/staff`.

## 5. Create your trial restaurant

On EC2, run the interactive bootstrap command. Use your own email address and enter a new owner password when prompted:

```sh
cd ~/dinebridge
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml exec api \
  python manage.py bootstrap_tenant \
  --tenant-slug my-restaurant --legal-name 'My Restaurant' \
  --brand-slug my-brand --brand-name 'My Restaurant' \
  --outlet-slug main --outlet-name 'Main Outlet' \
  --owner-email you@example.com
```

Sign in at `/staff`. Add a category and dish under **Menu**, enable **Accept new orders** under **Settings**, and add a table under **Tables**. Print or save its QR before closing the dialog. Scan that QR on a phone, place an order, and verify it appears in **Kitchen**. The local demo credentials are not copied to AWS and will not work there.

To enable **Polish with AI**, add an `OPENAI_API_KEY=...` line to the private `deploy/aws.env` on EC2, then recreate the API container. This is optional and uses your own OpenAI API account. Keep the key out of Git.

## 6. Operate or stop the trial

From `~/dinebridge` on EC2, inspect logs with `sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml logs --tail=100 api web`. To deploy code changes, commit and push on your Mac, then run these commands on EC2. For a private repository, prefix `git pull` with the same `GIT_SSH_COMMAND` used for cloning. Run migrations from the newly built image before starting the updated API:

```sh
cd ~/dinebridge
git pull --ff-only origin main
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml build api web
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml run --rm api python db/migrate.py
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml up -d api web
sudo docker compose --env-file deploy/aws.env -f compose.aws.yaml ps
```

The `media_data` volume holds uploaded menu photos and survives container recreation. Include it alongside PostgreSQL in your backups; `docker compose down --volumes` deletes both volumes.

Before stopping or terminating the instance, export the database to a separate safe location. EC2 termination removes the instance; an EBS root volume can also be deleted according to its delete-on-termination setting. Stop/termination and the associated disk, public IP, and Elastic IP have different billing behavior. Review the EC2 and Billing consoles when you finish the trial. This single-node setup does not include automated backup, monitoring, or high availability.
