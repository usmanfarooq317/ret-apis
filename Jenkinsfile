pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "usmanfarooq317/ret-api-dashboard"
        GIT_REPO = "https://github.com/usmanfarooq317/ret-apis"
    }

    triggers {
        githubPush()   // ✅ Auto build on every push to GitHub
    }

    stages {
        stage('Checkout Code') {
            steps {
                git branch: 'main', url: "${GIT_REPO}"
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "🚀 Building Docker Image..."
                    sh "docker build -t ${DOCKER_IMAGE}:latest -t ${DOCKER_IMAGE}:${BUILD_NUMBER} ."
                }
            }
        }

        stage('Push Docker Image to Docker Hub') {
            steps {
                script {
                    echo "📤 Pushing Image to Docker Hub..."
                    withCredentials([usernamePassword(
                        credentialsId: 'dockerhub-credentials',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh "echo $DOCKER_PASS | docker login -u $DOCKER_USER --password-stdin"
                        sh "docker push ${DOCKER_IMAGE}:latest"
                        sh "docker push ${DOCKER_IMAGE}:${BUILD_NUMBER}"
                    }
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                script {
                    echo "🚀 Deploying to EC2 Server (54.89.241.89)..."
                    sshagent(['ec2-ssh-key']) { // ✅ Use Jenkins credentials
                        sh '''
                        ssh -o StrictHostKeyChecking=no ubuntu@54.89.241.89 << 'EOF'
                        echo "✅ Connected to EC2"

                        # Stop and remove any running container
                        docker stop ret-api-dashboard || true
                        docker rm ret-api-dashboard || true

                        # Pull latest image from Docker Hub
                        docker pull usmanfarooq317/ret-api-dashboard:latest

                        # Start new container
                        docker run -d --name ret-api-dashboard -p 5000:5020 usmanfarooq317/ret-api-dashboard:latest

                        echo "✅ Deployment Successful on EC2!"
                        EOF
                        '''
                    }
                }
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline completed successfully!"
        }
        failure {
            echo "❌ Pipeline failed!"
        }
    }
}
