#!/usr/bin/env bash

source ~/miniconda3/etc/profile.d/conda.sh

create_this_env () {
	# $1 is the name of the new environment
	# $2 is path to environment yaml file	
	
	# Overwrite name of the environment set in the file
	cp ${2} temp_env.yml
	var="name: $1"
	sed -i '' "1s/.*/$var/" temp_env.yml > /dev/null 2>&1
	
	# Eventually remove environment if exists:
	if conda env list | grep $1; then
	    printf "$1 already exists, remove and re-create this environment...\n"
		# conda remove --quiet --name $1 --all --yes --json > tmp.json
		  conda remove --quiet --name $1 --all --yes --json > /dev/null 2>&1
	else
		  printf "Creating conda environment $1 ...\n"
	fi

	# Create the environment from file
	# conda env create --quiet --file temp_env.yml --json >> tmp.json
	conda env create --quiet --file temp_env.yml --json > /dev/null 2>&1
	
	# Clean-up
	/bin/rm tmp.json > /dev/null 2>&1
	/bin/rm temp_env.yml > /dev/null 2>&1


}


fix_kernel_path (){
  ENV=${1}

  kernelspec="$(jupyter kernelspec list | grep ${ENV})"
  echo "${kernelspec}"
  IFS=' ' read -ra ADDR <<< "$kernelspec"
  kernel_path="${ADDR[1]}"
  #echo "${kernel_path}"
  kernel_cfg_file="${kernel_path}/kernel.json"
#  echo "${kernel_cfg_file}"
  python_path="$(more ${kernel_cfg_file} | jq .argv[0] | sed 's/\"//g')"
  #echo ${python_path} | sed 's/"//g'
#  echo "${python_path}"
  DIR="$(dirname ${python_path})"
  FILE="$(basename ${python_path})"
  #echo "[${DIR}] [${FILE}]"
  IFS='/' read -r -a parts <<< "$DIR"
  #for index in "${!parts[@]}"
  #do
  #    echo "$index ${parts[index]}"
  #done
  #echo "${parts[-2]}"
  # We expect: /Users/gmaze/miniconda3/envs/<ENV>/bin
  if [ "${parts[-2]}" = ${ENV} ]; then
    echo "kernel spec OK"
  else
#    echo "NOT OK !"
    parts[-2]=${ENV}  # update with appropriate python path
    NEW_DIR=$(IFS='/' ; echo "${parts[*]}")
    new_python_path="${NEW_DIR}/${FILE}"

    while true; do
      printf "Replace: \n${python_path} \nwith: \n${new_python_path}\n"
      read -p "Do you confirm ? [Yy/Nn] " yn
      case $yn in
          [Yy]* )
            cp -f ${kernel_cfg_file} "${kernel_cfg_file}.bak"
            tmp=$(mktemp)
            jq --arg a "$new_python_path" '.argv[0] = $a' ${kernel_cfg_file} > "$tmp" && mv "$tmp" ${kernel_cfg_file}
            break;;
          [Nn]* ) exit;;
          * ) echo "Please answer yes [Yy] or no [Nn]";;
      esac
    done

  fi
}

add_to_ipykernel () {
  # Possibly add it the Jupyter kernels:
   conda activate ${1}
   echo ${1}
   python -m ipykernel install --user --name=$1

   # Check installation of the kernel:
   fix_kernel_path ${1}
}


POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
#    -n|--name)
#      NAME="$2"
#      shift # past argument
#      shift # past value
#      ;;
#    -f|--file)
#      FILE="$2"
#      shift # past argument
#      shift # past value
#      ;;
    -l|--list|-h|--help)
      echo "Possible environment options include:"
      echo "--all"
      echo "--py37dev"
      echo "--py37free"
      echo "--py38dev"
      echo "--py38free"
      echo "--py38small"
      exit 0
      ;;
    -a|--all)
      declare -A ENV_LIST
      ENV_LIST[argopy-tests-py37dev]="py3.7-dev.yml"
      ENV_LIST[argopy-tests-py37free]="py3.7-free.yml"
      ENV_LIST[argopy-tests-py38dev]="py3.8-dev.yml"
      ENV_LIST[argopy-tests-py38free]="py3.8-free.yml"
      ENV_LIST[argopy-tests-py38free-small]="py3.8-small-free.yml"
      shift # past argument
      ;;
    --py37dev)
      declare -A ENV_LIST
      ENV_LIST[argopy-tests-py37dev]="py3.7-dev.yml"
      shift # past argument
      ;;
    --py37free)
      declare -A ENV_LIST
      ENV_LIST[argopy-tests-py37free]="py3.7-free.yml"
      shift # past argument
      ;;
    --py38dev)
      declare -A ENV_LIST
      ENV_LIST[argopy-tests-py38dev]="py3.8-dev.yml"
      shift # past argument
      ;;
    --py38free)
      declare -A ENV_LIST
      ENV_LIST[argopy-tests-py38free]="py3.8-free.yml"
      shift # past argument
      ;;
    --py38small)
      declare -A ENV_LIST
      ENV_LIST[argopy-tests-py38free-small]="py3.8-small-free.yml"
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}" # restore positional parameters

for NAME in "${!ENV_LIST[@]}"
do
   :
   FILE=${ENV_LIST[$NAME]}
   create_this_env ${NAME} ${FILE}
   add_to_ipykernel ${NAME}
done

exit 0