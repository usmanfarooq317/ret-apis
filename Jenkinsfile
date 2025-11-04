pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "usmanfarooq317/ret-api-dashboard"
        GIT_REPO = "https://github.com/usmanfarooq317/ret-apis.git"
        EC2_USER = "ubuntu"
        EC2_HOST = "54.89.241.89"   
        EC2_KEY = "ec2-ssh-key"                    // Jenkins Secret (PEM)
    }

    triggers {
        githubPush()
    }

    stages {
        stage('Checkout Code') {
            steps {
                git branch: 'main',
                    url: "${GIT_REPO}",
                    credentialsId: 'github-token'
            }
        }

        stage('Determine New Version Tag') {
            steps {
                script {
                    // Get highest existing tag from Docker Hub:
                    def tags = sh(
                        script: "curl -s https://hub.docker.com/v2/repositories/${DOCKER_IMAGE}/tags/ | jq -r '.results[].name' | grep '^v[0-9]' || true",
                        returnStdout: true
                    ).trim().split('\n')

                    if (tags.size() == 0 || tags[0] == "") {
                        env.VERSION_TAG = "v1"
                    } else {
                        tags = tags.collect { it.replace('v', '').toInteger() }.sort()
                        env.VERSION_TAG = "v" + (tags[-1] + 1)
                    }

                    echo "✅ New version to push: ${env.VERSION_TAG}"
                }
            }
        }

        stage('Remove Old Local Images') {
            steps {
                sh """
                docker rmi -f ${DOCKER_IMAGE}:latest || true
                docker rmi -f ${DOCKER_IMAGE}:${VERSION_TAG} || true
                """
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${DOCKER_IMAGE}:latest ."
            }
        }

        stage('Login & Push Latest to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                    sh """
                    echo $PASS | docker login -u $USER --password-stdin
                    docker push ${DOCKER_IMAGE}:latest
                    """
                }
            }
        }

        stage('Tag & Push Versioned Image (vX)') {
            when { expression { currentBuild.currentResult == 'SUCCESS' } }
            steps {
                sh """
                docker tag ${DOCKER_IMAGE}:latest ${DOCKER_IMAGE}:${VERSION_TAG}
                docker push ${DOCKER_IMAGE}:${VERSION_TAG}
                """
            }
        }

        stage('Deploy on EC2 using docker-compose') {
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh-key', keyFileVariable: 'KEY')]) {
                    sh """
                    ssh -o StrictHostKeyChecking=no -i $KEY ${EC2_USER}@${EC2_HOST} '
                        cd /home/ubuntu/ret-apis || true

                        # Clone repo if not present
                        if [ ! -d "ret-apis" ]; then
                            git clone https://github.com/usmanfarooq317/ret-apis.git
                            cd ret-apis
                        else
                            cd ret-apis
                            git pull origin main
                        fi

                        docker-compose down || true
                        docker rm -f ret-api-dashboard || true
                        docker rmi -f ${DOCKER_IMAGE}:latest || true

                        docker pull ${DOCKER_IMAGE}:${VERSION_TAG}

                        sed -i "s|image:.*|image: ${DOCKER_IMAGE}:${VERSION_TAG}|g" docker-compose.yml

                        docker-compose up -d
                    '
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Build Success — Deployed version ${VERSION_TAG} to EC2."
        }
        failure {
            echo "❌ Build Failed — No new version tag created."
        }
    }
}
