# E2B Template for Next.js with 4C/4G
FROM e2bdev/base

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create project directory
WORKDIR /home/user/project

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install && npm cache clean --force

# Set permissions
RUN chown -R user:user /home/user
